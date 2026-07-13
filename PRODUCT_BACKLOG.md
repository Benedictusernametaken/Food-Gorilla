## Product Backlog

System name: DevOps Food Order App Project (**FoodGorilla**)

+------+---------------------------------------------------------+----+
| User | User Story                                              | S  |
| S    |                                                         | to |
| tory |                                                         | ry |
| ID   |                                                         | P  |
|      |                                                         | oi |
|      |                                                         | nt |
+======+=========================================================+====+
| 00   | **[Story 1: User Profile & Macro Calculator (Member     | 3  |
|      | 1)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a health-conscious customer, I want  |    |
|      | to input my physical metrics and fitness goals so that  |    |
|      | the system can automatically calculate my daily target  |    |
|      | calories and macronutrients.                            |    |
|      |                                                         |    |
|      | **CoS:** **Given** I am a new user completing my        |    |
|      | fitness onboarding, **when** I input my physical        |    |
|      | metrics and select a fitness goal, **then** the system  |    |
|      | should automatically calculate my target calories and   |    |
|      | macros and save them to my profile.                     |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   User can input age, gender, weight, height, and     |    |
|      |     activity level.                                     |    |
|      |                                                         |    |
|      | -   User can select a primary goal (e.g., Lose Weight,  |    |
|      |     Maintain, Gain Muscle).                             |    |
|      |                                                         |    |
|      | -   System calculates and displays daily target         |    |
|      |     Calories, Protein, Carbs, and Fats.                 |    |
|      |                                                         |    |
|      | -   Data is saved successfully to the user profile      |    |
|      |     database.                                           |    |
+------+---------------------------------------------------------+----+
| 01   | **[Story 2: Smart Metric-Filtered Menu (Member          | 3  |
|      | 2)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a fitness tracker user, I want to    |    |
|      | filter restaurant menus using specific nutritional      |    |
|      | sliders so that I can easily find meals that fit my     |    |
|      | remaining daily macros.                                 |    |
|      |                                                         |    |
|      | **CoS:** **Given** I am browsing the food court menu,   |    |
|      | **when** I adjust the protein slider to a minimum of    |    |
|      | 30g, **then** the interface should instantly hide all   |    |
|      | meals that contain less than 30g of protein without     |    |
|      | reloading the page.                                     |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   Home page displays a list of available restaurant   |    |
|      |     partners and meals.                                 |    |
|      |                                                         |    |
|      | -   Includes interactive range sliders for Calories,    |    |
|      |     Protein, Carbs, and Fats.                           |    |
|      |                                                         |    |
|      | -   Menu updates dynamically to show only items         |    |
|      |     matching the selected ranges.                       |    |
|      |                                                         |    |
|      | -   Displays the exact nutritional breakdown on each    |    |
|      |     food item card.                                     |    |
+------+---------------------------------------------------------+----+
| 02   | **[Story 3: Interactive Meal-Builder / CRUD (Member     | 5  |
|      | 3)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a strict macro-tracker, I want to    |    |
|      | customize the ingredients of a meal so that I can       |    |
|      | fine-tune its nutritional value to match my exact meal  |    |
|      | plan.                                                   |    |
|      |                                                         |    |
|      | **CoS:** **Given** I have selected a custom healthy     |    |
|      | meal option, **when** I increase the portion size of an |    |
|      | ingredient (e.g., adding extra chicken breast),         |    |
|      | **then** the system should dynamically update both the  |    |
|      | total meal price and the cumulative macro counters in   |    |
|      | my active cart session.                                 |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   User can click a meal to open a customization       |    |
|      |     interface.                                          |    |
|      |                                                         |    |
|      | -   User can add, remove, or increase portion sizes of  |    |
|      |     specific ingredients (e.g., +100g chicken breast).  |    |
|      |                                                         |    |
|      | -   Modifying ingredients dynamically recalculates the  |    |
|      |     total meal price and total macros in real-time.     |    |
|      |                                                         |    |
|      | -   The customized item can be successfully added to    |    |
|      |     the checkout cart.                                  |    |
+------+---------------------------------------------------------+----+
| 03   | **[Story 4: Daily Fitness Tracking Dashboard (Member    | 3  |
|      | 4)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a user tracking my fitness progress, |    |
|      | I want a visual dashboard that updates when I order     |    |
|      | food so that I can see how much of my daily macro       |    |
|      | allowance I have left.                                  |    |
|      |                                                         |    |
|      | **CoS:** **Given** I am viewing my daily fitness        |    |
|      | progress charts, **when** a new food order is           |    |
|      | successfully checked out, **then** the dashboard should |    |
|      | instantly add those macros to my daily total and turn   |    |
|      | the progress bar red if I have exceeded my daily target |    |
|      | limit.                                                  |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   Dashboard displays visual progress bars for         |    |
|      |     Calories, Protein, Carbs, and Fats.                 |    |
|      |                                                         |    |
|      | -   Progress bars accurately reflect total consumed vs. |    |
|      |     total target allowances.                            |    |
|      |                                                         |    |
|      | -   Placing a successful food order automatically adds  |    |
|      |     those metrics to the daily total.                   |    |
|      |                                                         |    |
|      | -   Warns the user visually if an order will cause them |    |
|      |     to exceed their daily target limits.                |    |
+------+---------------------------------------------------------+----+
| 04   | **[Story 5: Vendor Management Portal (Member            | 5  |
|      | 5)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a restaurant partner, I want an      |    |
|      | interface to manage my menu items and input their exact |    |
|      | nutritional values so that fitness users can discover   |    |
|      | my food.                                                |    |
|      |                                                         |    |
|      | **CoS:** **Given** I am a restaurant partner logged     |    |
|      | into the vendor portal, **when** I submit a new menu    |    |
|      | item with its price and exact macro breakdown, **then** |    |
|      | the item should immediately populate and become         |    |
|      | searchable on the customer-facing marketplace.          |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   Vendor can log into a separate merchant dashboard.  |    |
|      |                                                         |    |
|      | -   Vendor can create, read, update, and delete (CRUD)  |    |
|      |     their menu items.                                   |    |
|      |                                                         |    |
|      | -   Each item form mandates fields for Calories,        |    |
|      |     Protein, Carbs, and Fats alongside price.           |    |
|      |                                                         |    |
|      | -   Vendor can toggle an item\'s availability status    |    |
|      |     (In Stock / Out of Stock).                          |    |
+------+---------------------------------------------------------+----+
| 05   | **[Story 6: Scheduled Subscription Engine (Member       | 5  |
|      | 6)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a busy professional, I want to       |    |
|      | schedule recurring meal deliveries for the entire week  |    |
|      | so that I don\'t have to manually order every single    |    |
|      | day to stay on track.                                   |    |
|      |                                                         |    |
|      | **CoS:** **Given** I am setting up my healthy meal plan |    |
|      | for the upcoming week, **when** I allocate specific     |    |
|      | macro-compliant meals to individual days on the         |    |
|      | calendar interface, **then** the system should generate |    |
|      | a clear weekly delivery summary and aggregate the total |    |
|      | subscription cost.                                      |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   User can access a weekly calendar planner interface |    |
|      |     (Monday--Friday).                                   |    |
|      |                                                         |    |
|      | -   User can assign specific macro-compliant meals to   |    |
|      |     specific days and delivery times.                   |    |
|      |                                                         |    |
|      | -   System generates a summary of the weekly            |    |
|      |     subscription schedule and total cost.               |    |
|      |                                                         |    |
|      | -   User can modify or cancel a scheduled day\'s meal   |    |
|      |     before a set cutoff time.                           |    |
+------+---------------------------------------------------------+----+
| 06   | **[Story 7: User Authentication (Sign Up & Login)       | 2  |
|      | (Member 1)]{.underline}**                               |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a user, I want to register for an    |    |
|      | account and log in so that I can securely access my     |    |
|      | profile, track my macros, and use the system features.  |    |
|      |                                                         |    |
|      | **CoS:** **Given** Given I am either a new or returning |    |
|      | user,                                                   |    |
|      |                                                         |    |
|      | when I enter my registration or login credentials,      |    |
|      |                                                         |    |
|      | then the system should either create a new account or   |    |
|      | authenticate me and grant access to my account.         |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   User can:                                           |    |
|      |                                                         |    |
|      |     -   Register with username, email, and password     |    |
|      |                                                         |    |
|      |     -   Log in using email/username and password        |    |
|      |                                                         |    |
|      | -   Password is securely hashed and stored              |    |
|      |                                                         |    |
|      | -   Email must be unique for new accounts               |    |
|      |                                                         |    |
|      | -   System validates login credentials                  |    |
|      |                                                         |    |
|      | -   Invalid inputs show error messages                  |    |
|      |                                                         |    |
|      | -   Successful login creates a session/token            |    |
|      |                                                         |    |
|      | -   User is redirected to dashboard/profile             |    |
+------+---------------------------------------------------------+----+
| 07   | **[Story 8: Vendor Account Management (Member           | 3  |
|      | 5)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a restaurant partner, I want to      |    |
|      | register and log in to my vendor account so that I can  |    |
|      | manage my menu items securely.                          |    |
|      |                                                         |    |
|      | **CoS:** **Given I am a new or existing restaurant      |    |
|      | partner,**                                              |    |
|      |                                                         |    |
|      | **when I register or log in with my credentials,**      |    |
|      |                                                         |    |
|      | **then the system should authenticate me and grant      |    |
|      | access to the vendor portal.**                          |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      |  Vendor can register with:                             |    |
|      |                                                         |    |
|      | -   Business name                                       |    |
|      |                                                         |    |
|      | -   Email                                               |    |
|      |                                                         |    |
|      | -   Password                                            |    |
|      |                                                         |    |
|      |  Vendor login validates credentials                    |    |
|      |                                                         |    |
|      |  Password is securely hashed                           |    |
|      |                                                         |    |
|      |  Successful login grants access to **Vendor Management |    |
|      | Portal**                                                |    |
|      |                                                         |    |
|      |  Each vendor is assigned a unique vendor_id            |    |
|      |                                                         |    |
|      |  Vendor account links to their meals in the Meals      |    |
|      | table                                                   |    |
+------+---------------------------------------------------------+----+
| 08   | **[Story 9: Order and Checkout System (Member           | 5  |
|      | 2)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a user, I want to place an order and |    |
|      | checkout my selected meals so that my purchases are     |    |
|      | recorded and my daily macro intake is updated.          |    |
|      |                                                         |    |
|      | **CoS:** **Given** Given I am either a new or returning |    |
|      | user,                                                   |    |
|      |                                                         |    |
|      | when I enter my registration or login credentials,      |    |
|      |                                                         |    |
|      | then the system should either create a new account or   |    |
|      | authenticate me and grant access to my account.         |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      | -   User can:                                           |    |
|      |                                                         |    |
|      |     -   Register with username, email, and password     |    |
|      |                                                         |    |
|      |     -   Log in using email/username and password        |    |
|      |                                                         |    |
|      | -   Password is securely hashed and stored              |    |
|      |                                                         |    |
|      | -   Email must be unique for new accounts               |    |
|      |                                                         |    |
|      | -   System validates login credentials                  |    |
|      |                                                         |    |
|      | -   Invalid inputs show error messages                  |    |
|      |                                                         |    |
|      | -   Successful login creates a session/token            |    |
|      |                                                         |    |
|      | -   User is redirected to dashboard/profile             |    |
+------+---------------------------------------------------------+----+
| 09   | **[Story 10: Cart Management (Member 3)]{.underline}**  | 3  |
|      |                                                         |    |
| (N   | **User Story:** As a user, I want to add customized     |    |
| ame) | meals to a cart so that I can review and modify my      |    |
|      | selections before checking out.                         |    |
|      |                                                         |    |
|      | **CoS:** **Given I am browsing or customizing meals,\   |    |
|      | when I add items to my cart,\                           |    |
|      | then the system should store and display those items    |    |
|      | with updated totals.**                                  |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      |  User can:                                             |    |
|      |                                                         |    |
|      | -   Add meals to cart                                   |    |
|      |                                                         |    |
|      | -   Remove meals from cart                              |    |
|      |                                                         |    |
|      | -   Modify quantities/customization                     |    |
|      |                                                         |    |
|      |  Cart updates:                                         |    |
|      |                                                         |    |
|      | -   Total price                                         |    |
|      |                                                         |    |
|      | -   Total macros                                        |    |
|      |                                                         |    |
|      |  Cart persists during session                          |    |
|      |                                                         |    |
|      |  Cart is cleared after successful checkout             |    |
+------+---------------------------------------------------------+----+
| 10   | **[Story 11: Daily Log Tracking (Member                 | 5  |
|      | 4)]{.underline}**                                       |    |
| (N   |                                                         |    |
| ame) | **User Story:** As a user, I want my daily nutritional  |    |
|      | intake to be automatically recorded so that I can track |    |
|      | my progress over time.                                  |    |
|      |                                                         |    |
|      | **CoS:** **Given** Given I have completed a food order, |    |
|      |                                                         |    |
|      | when the order is processed,                            |    |
|      |                                                         |    |
|      | then the system should update my daily nutritional log  |    |
|      | with the consumed values.                               |    |
|      |                                                         |    |
|      | **Acceptance Criteria:**                                |    |
|      |                                                         |    |
|      |  Each order updates:                                   |    |
|      |                                                         |    |
|      | -   Calories                                            |    |
|      |                                                         |    |
|      | -   Protein                                             |    |
|      |                                                         |    |
|      | -   Carbs                                               |    |
|      |                                                         |    |
|      | -   Fats                                                |    |
|      |                                                         |    |
|      |  Logs are stored per:                                  |    |
|      |                                                         |    |
|      | -   User                                                |    |
|      |                                                         |    |
|      | -   Date                                                |    |
|      |                                                         |    |
|      |  Dashboard reflects updated totals immediately         |    |
+------+---------------------------------------------------------+----+