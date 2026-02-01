# MealPlan Assistant (Rasa chatbot) by Panagiotis FASOULIDIS

**MealPlan Assistant** is a task-oriented chatbot built with **Rasa**. The reason why I developed this specific Rasa Chatbot was to help a user quickly decide *what to eat*, offer *recipe ideas* based on what they already have at home and provide *basic nutrition information* without having to search multiple websites.

This project was developed in the context of the course **“Special Topics in Language Technology: Multimodal and Dialogue Systems and Voice Assistants”** (MSc Language Technology) and follows the assignment requirements for a Task-Oriented Dialog System Prototype: multiple distinct interaction scenarios, a mock task execution, integrations with real-world data sources and robust error handling.

## Domain and motivation

Meal planning is a small everyday problem that becomes annoying very quickly: people often want suggestions that are immediate, simple and usable, without spending time scrolling through recipes or nutrition pages. The motivation behind this bot is to provide “fast help” in three common situations:

1. The user wants a **ready meal plan** (for today, tomorrow, or a full week) without overthinking it.
2. The user has an ingredient and wants **recipe ideas** that actually exist in a real recipe database.
3. The user wants **nutrition values** (calories/macros) for a food item, in a way that is quick and easy to understand.

Even though the assistant is simple by design, it still demonstrates the typical structure of a task-oriented system: intent classification, slot filling via forms, custom actions and integration with external data sources.

## Implemented scenarios (3 distinct interaction scenarios)

### Scenario 1 — Meal plan suggestions (mock task execution)

In the first scenario, the user asks the assistant for a meal plan. The dialogue can start in a generic way (“I want a meal plan”) or directly request a time range (“meal plan for today”, “meal plan for tomorrow”, “weekly meal plan”). 

This scenario is implemented with mock actions:
- `action_meal_plan_today`
- `action_meal_plan_tomorrow`
- `action_weekly_meal_plan`

The assistant returns a predefined plan (breakfast/lunch/dinner or a simple weekly outline). This is intentionally deterministic: the goal is to **simulate task execution** in a reliable way, similar to how an early prototype might work before being connected to a real meal-planning engine or a database.

### Scenario 2 — Find recipes by ingredient (real-world API integration)

In the second scenario, the user wants recipe ideas based on an ingredient (e.g. “recipes with chicken”). Since users may provide incomplete information, the assistant uses a form (`recipe_form`) to ensure the `ingredient` slot is collected properly. 

Once the ingredient is known, the assistant executes `action_find_recipes` which queries **TheMealDB** API in two steps:
1. It first retrieves candidate meals that contain the ingredient.
2. Then it requests detailed information for one of the results (title, ingredients, instructions).

The response is based on the API output and formatted in a user-friendly way, so the content is dynamic: if the user changes the ingredient, the assistant fetches different results.

### Scenario 3 — Nutrition information for foods (real-world dataset integration)

In the third scenario, the user asks for nutrition values such as calories or macros (e.g., “calories in banana”, “macros for oats”). As with recipes, the assistant uses a form (`nutrition_form`) to reliably collect the `food` slot.

The assistant then runs `action_get_nutrition`, which loads a **local CSV nutrition dataset** (from Kaggle) located at:
`resources/food_nutrition_dataset_kaggle.csv`

To make this scenario usable in real conversations, the matching is not limited to exact string equality. The implementation supports:
- normalization (case/spacing/punctuation),
- substring matching (when users type partial names),
- fuzzy matching (to tolerate spelling differences).

The final response provides calories and available macros per 100g (based on the dataset), clearly formatted for quick reading.

## Integrated data sources (what they are and why)

The assistant integrates two real-world data sources in two distinct scenarios:

**1) TheMealDB API (external data source)**  
This source is used for recipe retrieval in Scenario 2. It was chosen because it is publicly accessible, lightweight to integrate and produces dynamic results. It demonstrates the chatbot’s ability to send requests, parse JSON and generate responses based on live external data.

**2) Kaggle nutrition dataset (local CSV dataset)**  
This source is used in Scenario 3. A structured local dataset is ideal for deterministic, grounded responses: the assistant can give nutrition values without relying on an online service and the logic is transparent and reproducible. 


## Error handling and robustness

Because task-oriented bots can fail in practical ways (network issues, missing slots, unexpected user messages), the implementation includes robustness mechanisms:

- **API failures and timeouts:** recipe requests are wrapped in `try/except` blocks with explicit timeouts. If the API is unavailable, the assistant responds with a clear message instead of crashing.
- **No results:** when the API returns no recipes for a given ingredient, the assistant explicitly informs the user and encourages them to try a different ingredient. Similarly, if the nutrition dataset has no match, the assistant reports that no nutrition data was found.
- **Slot validation through forms:** both `recipe_form` and `nutrition_form` validate user input using `validate_recipe_form` and `validate_nutrition_form` to avoid empty or unusable values.
- **Out-of-scope messages and insults:** the bot includes explicit intents and responses to keep the interaction controlled and polite and a fallback response for low-confidence NLU predictions.

## Challenges during implementation (and how I handled them)

### 1) LLM-based generation with Ollama was inconsistent in Rasa actions

Initially, I tried using a local LLM (via Ollama) in order to generate more natural and flexible responses.  
In practice, this approach proved unreliable inside Rasa actions. The request–response loop was not stable:

- responses were sometimes slow enough that the action call felt “stuck”,  
- occasionally the response arrived too late or timed out,  
- overall, the dialogue flow felt unpredictable for a task-oriented system.

**What I did instead:**  
I switched to a deterministic approach, where responses are generated based on structured API outputs and dataset values, combined with lightweight formatting. This made the assistant significantly faster and more predictable.

**Future improvement idea:**  
LLM-based generation could be reintroduced as an optional layer (for example asynchronously or with caching), so that it never blocks the core dialogue logic.


### 2) Intent overlap: `provide_food` vs `nutrition_info`

Users often provide very short messages such as just a food name (e.g., “banana”), which can be ambiguous and confuse intent classification. This created overlap between general nutrition requests and direct food mentions.

This issue was addressed by:
- creating separate intents (`nutrition_info` and `provide_food`),  
- using a form (`nutrition_form`) so the bot can recover even if the first user message is minimal,  
- adding a rule so that if the user provides a food directly, the bot automatically enters the nutrition flow.

This design keeps the dialogue coherent even when user input is underspecified.


### 3) Data variability in the Kaggle dataset (column naming & formatting)

Real-world datasets are rarely perfectly clean or consistent. The nutrition CSV used in this project contains variations in column names, missing values and different encodings.

To make the system robust, I implemented:
- automatic column detection (`_pick_col`) using candidate column names,  
- safe numeric parsing (`_to_float`) and text normalization (`_norm_food_name`),  
- fallback encodings when loading the CSV file.

These mechanisms prevent runtime crashes and significantly improve matching reliability across different food entries.

## Example interactions (chatbot interface)

To demonstrate that the system works both at the interface level and at the backend level, example interactions are shown from two different perspectives: a graphical user interface and the Rasa terminal.

**Graphical interface (UI prototype):**  
A simple chat interface was designed (e.g., using Figma / web-based mockup) to illustrate how the chatbot could be embedded in a real application. This interface shows typical user interactions such as requesting meal plans, asking for recipes, and querying nutrition information. The goal of this UI is not to build a full product, but to provide a realistic visualization of how users would interact with the system.

**Terminal interface (Rasa shell):**  
The same scenarios were also tested directly through the Rasa shell. This demonstrates that the dialogue logic, intent classification, slot filling, and custom actions work correctly at the system level, independently of any graphical interface.

The examples include:
- normal task-oriented flows (meal plans, recipes, nutrition),
- out-of-scope questions (e.g., unrelated topics),
- error cases (e.g., no results found, unavailable API),
- and recovery behavior through forms and fallback responses.

Screenshots from both the UI prototype and the terminal runs are included in the `screenshots/` folder and in the presentation, as evidence of correct system behavior.

## Credits and data sources

This project makes use of the following external resources:

- **TheMealDB API**  
  https://www.themealdb.com  
  Used for retrieving real recipe data based on ingredients.

- **Kaggle Nutrition Dataset**  
  [https://www.kaggle.com ](https://www.kaggle.com/datasets/adilshamim8/daily-food-and-nutrition-dataset) 
  Used as a local CSV dataset for nutritional information (calories and macronutrients).

These sources were selected because they are publicly available, easy to integrate, and suitable for demonstrating real-world data usage in a task-oriented dialogue system.
