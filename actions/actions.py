from typing import Any, Dict, List, Text, Optional

# Imports
import os
import json
import difflib
import pandas as pd
import requests

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.forms import FormValidationAction

# Nutrition Dataset CSV (from Kaggle)
# Used for nutrition information (calories & macros)

KAGGLE_CSV = os.path.join("resources", "food_nutrition_dataset_kaggle.csv")

_DATA_LOADED = False
_KAGGLE_INDEX: Dict[str, Dict[str, Any]] = {}
_ALL_KEYS: List[str] = []


# Helper Functions: Entity extraction, Text normalization, Dataset handling utilities

def _latest_entity_value(tracker: Tracker, entity_name: Text) -> Optional[Text]:
    """Extracts the most recent entity value from user input"""
    ents = tracker.latest_message.get("entities", []) or []
    for e in ents:
        if e.get("entity") == entity_name and e.get("value"):
            return str(e.get("value")).strip()
    return None


def _norm_food_name(s: str) -> str:
    """Normalizes food names for matching (case, punctuation, spaces)"""
    if s is None:
        return ""
    s = str(s).strip()
    s = s.strip(" .,!?:;\"'()[]{}")
    return " ".join(s.upper().split())


def _to_float(x: Any) -> Optional[float]:
    """Safely converts values to float"""
    try:
        if x is None:
            return None
        if isinstance(x, str) and not x.strip():
            return None
        return float(x)
    except Exception:
        return None


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Finds the best matching column name from a list of candidates"""
    cols = list(df.columns)
    cols_lower = {c.lower(): c for c in cols}

    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]

    for c in cols:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c

    return None

# Dataset standardization and loading: Handles different column names, normalizes food items, builds a searchable index
def _standardize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    item_col = _pick_col(df, ["item", "food", "name", "description"])
    kcal_col = _pick_col(df, ["calories", "kcal", "energy_kcal"])
    protein_col = _pick_col(df, ["protein"])
    fat_col = _pick_col(df, ["fat"])
    carbs_col = _pick_col(df, ["carbs", "carbohydrate"])

    if not item_col or not kcal_col:
        raise ValueError("Missing required nutrition columns")

    out = pd.DataFrame()

    out["item"] = df[item_col].astype(str).str.strip()
    out["calories"] = pd.to_numeric(df[kcal_col], errors="coerce")
    out["protein"] = pd.to_numeric(df[protein_col], errors="coerce") if protein_col else None
    out["fat"] = pd.to_numeric(df[fat_col], errors="coerce") if fat_col else None
    out["carbs"] = pd.to_numeric(df[carbs_col], errors="coerce") if carbs_col else None

    out["item_norm"] = out["item"].map(_norm_food_name)

    out = out.dropna(subset=["item", "calories"])
    out = out.drop_duplicates(subset=["item_norm"])

    return out


def _read_kaggle_csv(path: str) -> pd.DataFrame:
    """Attempts to read CSV using multiple encodings"""
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, engine="python", on_bad_lines="skip")
        except Exception:
            continue

    raise RuntimeError("Cannot read Kaggle CSV file")


def _load_local_dataset() -> None:
    """Loads and indexes the nutrition dataset once"""
    global _DATA_LOADED, _KAGGLE_INDEX, _ALL_KEYS

    if _DATA_LOADED:
        return

    if not os.path.exists(KAGGLE_CSV):
        raise FileNotFoundError(KAGGLE_CSV)

    raw = _read_kaggle_csv(KAGGLE_CSV)
    df = _standardize_dataset(raw)

    for _, r in df.iterrows():

        key = r["item_norm"]

        _KAGGLE_INDEX[key] = {
            "name": r["item"],
            "kcal": _to_float(r["calories"]),
            "protein": _to_float(r.get("protein")),
            "carbs": _to_float(r.get("carbs")),
            "fat": _to_float(r.get("fat")),
        }

    _ALL_KEYS = list(_KAGGLE_INDEX.keys())
    _DATA_LOADED = True


def _lookup_food(food: str) -> Optional[Dict[str, Any]]:
    """Finds a food item using: exact match, substring match, fuzzy matching"""
    q = _norm_food_name(food)

    if q in _KAGGLE_INDEX:
        return _KAGGLE_INDEX[q]

    contains = [k for k in _ALL_KEYS if q in k]
    if contains:
        return _KAGGLE_INDEX[contains[0]]

    close = difflib.get_close_matches(q, _ALL_KEYS, n=1)

    if close:
        return _KAGGLE_INDEX.get(close[0])

    return None


# Form validation: Ensures that the required slots are filled correctly

class ValidateRecipeForm(FormValidationAction):
    """Validates ingredient input for recipe search"""
    def name(self) -> Text:
        return "validate_recipe_form"

    def validate_ingredient(self, slot_value, dispatcher, tracker, domain):

        v = str(slot_value).strip()

        if len(v) < 2:
            dispatcher.utter_message(text="Please give a valid ingredient.")
            return {"ingredient": None}

        return {"ingredient": v}


class ValidateNutritionForm(FormValidationAction):
    """Validates food input for nutrition information"""
    def name(self) -> Text:
        return "validate_nutrition_form"

    def validate_food(self, slot_value, dispatcher, tracker, domain):

        v = str(slot_value).strip()

        if len(v) < 2:
            dispatcher.utter_message(text="Please give a valid food name.")
            return {"food": None}

        return {"food": v}


# Meal Plans (mock)

class ActionMealPlanToday(Action):

    def name(self):
        return "action_meal_plan_today"

    def run(self, dispatcher, tracker, domain):

        plan = [
            "Breakfast: Yogurt + oats",
            "Lunch: Chicken salad",
            "Dinner: Lentil soup",
        ]

        dispatcher.utter_message(
            text="Today's meal plan:\n- " + "\n- ".join(plan)
        )

        return []


class ActionMealPlanTomorrow(Action):
    def name(self):
        return "action_meal_plan_tomorrow"

    def run(self, dispatcher, tracker, domain):

        plan = [
            "Breakfast: Omelette",
            "Lunch: Tuna wrap",
            "Dinner: Rice + veggies",
        ]

        dispatcher.utter_message(
            text="Tomorrow's meal plan:\n- " + "\n- ".join(plan)
        )

        return []


class ActionWeeklyMealPlan(Action):
    def name(self):
        return "action_weekly_meal_plan"

    def run(self, dispatcher, tracker, domain):

        plan = {
            "Mon": "Chicken + rice",
            "Tue": "Pasta",
            "Wed": "Soup",
            "Thu": "Salad",
            "Fri": "Fish",
            "Sat": "Beans",
            "Sun": "Roast chicken",
        }

        lines = [f"{d}: {m}" for d, m in plan.items()]

        dispatcher.utter_message(
            text="Weekly plan:\n" + "\n".join(lines)
        )

        return []



# Recipes

class ActionFindRecipes(Action):
    def name(self):
        return "action_find_recipes"

    def run(self, dispatcher, tracker, domain):

        ing = _latest_entity_value(tracker, "ingredient") or tracker.get_slot("ingredient")

        if not ing:
            dispatcher.utter_message(text="Which ingredient?")
            return []

        ing = ing.strip()

        # First API call: get list of meals that contain the ingredient
        try:
            r = requests.get(
                "https://www.themealdb.com/api/json/v1/1/filter.php",
                params={"i": ing},
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
        except Exception:
            dispatcher.utter_message(text="Recipe service unavailable.")
            return []

        meals = data.get("meals")

        if not meals:
            dispatcher.utter_message(text="😕 I couldn’t find any recipes using this ingredient. How would you like to continue?")
            return []

        meal_id = meals[0]["idMeal"]

        # Second API call: get detailed recipe information
        try:
            r2 = requests.get(
                "https://www.themealdb.com/api/json/v1/1/lookup.php",
                params={"i": meal_id},
                timeout=10
            )
            r2.raise_for_status()
            details = r2.json()
        except Exception:
            dispatcher.utter_message(text="Could not load recipe details.")
            return []

        meal = details["meals"][0]

        title = meal["strMeal"]
        instructions = meal["strInstructions"]

        # Parse ingredients and measurements from TheMealDB
        ingredients = []

        for i in range(1, 21):

            ing = meal.get(f"strIngredient{i}")
            meas = meal.get(f"strMeasure{i}")

            if ing and ing.strip():
                ingredients.append(f"- {meas} {ing}".strip())

        msg = (
            f"🍽️ {title}\n\n"
            f"Ingredients:\n" + "\n".join(ingredients) +
            f"\n\nInstructions:\n{instructions[:700]}"
        )

        dispatcher.utter_message(text=msg)

        return [SlotSet("ingredient", None)]


# Nutrition Action: retrieves nutrition information from local CSV dataset, supports approximate matching & normalization

class ActionGetNutrition(Action):
    def name(self):
        return "action_get_nutrition"

    def run(self, dispatcher, tracker, domain):

        food = _latest_entity_value(tracker, "food") or tracker.get_slot("food")

        if not food:
            dispatcher.utter_message(text="Which food?")
            return []

        try:
            _load_local_dataset()
        except Exception:
            dispatcher.utter_message(text="Nutrition database unavailable.")
            return []

        hit = _lookup_food(food)

        if not hit:
            dispatcher.utter_message(text="No nutrition data found.")
            return []
        
        # create nutrition response
        parts = []

        if hit["kcal"]:
            parts.append(f"Calories: {hit['kcal']} kcal")

        if hit["protein"]:
            parts.append(f"Protein: {hit['protein']} g")

        if hit["carbs"]:
            parts.append(f"Carbs: {hit['carbs']} g")

        if hit["fat"]:
            parts.append(f"Fat: {hit['fat']} g")

        dispatcher.utter_message(
            text=f"Nutrition for {hit['name']} (per 100g):\n- " + "\n- ".join(parts)
        )

        return [SlotSet("food", None)]
