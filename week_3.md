# **Week 3: Minecraft Building Logic**

Welcome back! This week we're taking the JSON build plan Claude generated and actually executing it making your bot place real blocks in Minecraft. By the end of this week, you'll have a full end-to-end pipeline: upload an image in Streamlit, get a build plan from Claude, click a button, and watch your bot construct it block by block in-game.

---

### **1. Validating JSON with Pydantic Models**

Before sending any build instructions to the bot, we want to make sure the data is well-formed. That's where your `Block` and `MinecraftBuild` Pydantic models come in that we made last week. These models validate the JSON at runtime so you catch bad data before it ever reaches Minecraft.

**1.1 How the Models Work**

You already have these defined in `models.py`:

Think of these classes as a schema definition with free runtime validation. At a higher level, a schema gives structure to an object like your block. If Claude returns a block with a missing coordinate or a wrong type, Pydantic will raise an error immediately rather than silently passing bad data to the bot.

**1.2 Parsing and Validating Claude's Output**

Once you have the raw JSON string from Claude, parse and validate it like this before you even try to build:

```python
import json
from pydantic import ValidationError
from models import MinecraftBuild

def complete_schematic(data):
    # in case data is a string
    if not isinstance(data, dict):
        # Find the last completed object
        last_brace = data.rfind("}")
        if last_brace == -1:
            return None

        trimmed = data[: last_brace + 1] # get all the completed blocks
        # Close blocks array and top-level object if missing
        trimmed = trimmed.rstrip()

        if not trimmed.endswith("]}"):
            trimmed += "]}"

        return json.loads(trimmed)

    return data  # complete data
```

If this returns `None`, you know something went wrong before you ever try to place a single block. Add this function to your `app.py` file at the top or make a utils file. **This function is crucial because when we keep the LLM tokens low, sometimes the build gets cut off in the middle of a block.**

---

### **2. The `place_block` Function**

Create a new file called `bot_skills.py` or something similar. Follow the TODOs below to finish the function. You will be using the Minecraft `/setblock` [command](https://minecraft.wiki/w/Commands/setblock):

```python
def place_block(bot, block_type, x, y, z, direction=False):
    valid_directions = {"north", "south", "east", "west"}

    # TODO: Check if direction is a valid facing direction (i.e. it's in valid_directions)

        # TODO: Format the /setblock command as a string, including the facing property
        #       e.g. /setblock {x} {y} {z} {block_type}[facing={direction}]

    # TODO: If direction is not valid, format the /setblock command without a facing property
    #       e.g. /setblock {x} {y} {z} {block_type}

    # TODO: Send the command using bot.chat()
```

A few things to understand here:

- The bot must have operator permissions in-game for `/setblock` to work. That is why we enabled cheats in an earlier lesson
- Coordinates are absolute world coordinates, not relative to the bot's position
- The `facing` field only applies to directional blocks like stairs, doors, and furnaces

**2.1 Add a `build_from_json` Function**

Now write a function that iterates over a full `MinecraftBuild` and places every block. Add this to `bot_skills.py`:

```python
# TODO: you may have to add imports

def build_from_json(bot, json_data):
    pos = bot.entity.position
    base_x = int(pos.x) # We have to translate the world coordinates to be relative to the bot
    base_y = int(pos.y)
    base_z = int(pos.z)

    # Parse the JSON data into a MinecraftBuild instance
    minecraft_build = MinecraftBuild.model_validate(
        json_data
    )  # class that parses and holds json using BaseModel

    for block in minecraft_build.blocks:
        direction = getattr(block, "facing", False)
        place_block(
            bot,
            block.block_type,
            block.x + base_x,
            block.y + base_y,
            block.z + base_z,
            direction,
        )
```

---

### **3. Adding the `/build` Endpoint to Flask**

Now wire the building logic into your Flask back end so Streamlit can trigger a build with a single API call.

**3.1 Update `app.py`**

Add a `/build` endpoint that accepts a JSON body, validates it, and calls `build_from_json`:

```python
@app.route("/build", methods=["POST"])
def build():
    # TODO: Check if BOT_INSTANCE is None. If so, return a 400 JSON error with key "error" and value "no_bot" or something similar

    # TODO: Get the JSON body from the request using request.get_json()

    # TODO: Call complete_schematic(data) to validate and fill in any missing blocks.
    #       If it returns None (invalid JSON), fall back to loading "../schematics/triangle.json" from disk
    #       Hint: open the file with open(), then use json.load() to parse it

    # TODO: Call build_from_json with the bot instance's .bot attribute and the data

    # TODO: Return a JSON response with status "built" and the number of blocks placed
    #       Hint: use data.get("blocks", []) to safely get the block list
```

**Note:** the `triangle.json` mentioned in the code above will be provided in the repo

**3.2 Enable Hot Reloading (optional)**

Instead of restarting Flask manually every time you make a change, enable hot reloading by updating how you run the app. In your terminal, run:

```bash
flask --app app.py run --debug
```

Or update the bottom of `app.py`:

```python
if __name__ == "__main__":
    app.run(debug=True)
```

With `debug=True`, Flask will automatically restart whenever you save a change to your Python files.

---

### **4. Organizing Streamlit Helper Functions**

Your `main.py` is starting to get long. This week, move helper functions into a dedicated `utils.py` file to keep things clean.

**4.1 What Goes in `utils.py`**

Move or add these functions into `utils.py`:

- `resize_image(img)` — already exists from last week
- `complete_schematic(data)` — the validation function from section 1.2
- `call_build(button)` — a new function that POSTs to your `/build` endpoint (see below)

```python
import requests
import streamlit as st

def call_build(button=True): # This button parameter will come in handy during a later week
    url = "http://localhost:5000/build"

    data = st.session_state.get("build_data")
    try:
        response = requests.post(url, json=data)  # Make the POST request
        if response.status_code == 200:
            data = response.json()
            st.session_state["api_data"] = data  # Store the result in session state
            num_blocks = data.get("blocks")
            if button:
                st.success(f"Build call successful! Blocks placed: {num_blocks}")
        else:
            st.error(f"Build call failed with status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {e}")
```

**4.2 Importing in `main.py`**

At the top of `main.py`, import from `utils.py`:

```python
# from utils import ...
```

---

### **5. Wiring Up the Build Button in Streamlit**

Update `main.py` to display the JSON output and add a **Build in Minecraft** button that triggers the `/build` call.

1. Store the result from calling the analyzer function in `st.session_state.build_data`
2. Display the JSON and call the build function if the button is clicked:

```python
# This goes outside the Analyze button block
if st.session_state.build_data is not None:
    st.code(st.session_state.build_data, language="json")

    if st.button("BUILD"):
        call_build()
```

3. Initialize the build data on the session state at the top of `main`

```python
if "build_data" not in st.session_state:
    st.session_state.build_data = None
```

---

### **6. Testing Your Pipeline End to End**

**6.1 Pre-Flight Checklist**

Before testing, make sure:

- Flask is running
- Streamlit is running in a separate terminal
- Your bot has been spawned via the **Start Bot** button

**6.2 What to Test With**

Use the same simple images ideas from last week: a small house, a tower, or basic pixel art. Keep your `max_tokens` low (1024–2048) while testing, so you don't accidentally generate a 500-block build and waste tokens.

**6.3 What "Success" Looks Like**

- The JSON displays in Streamlit with no parse errors
- Clicking **Build in Minecraft** sends the request and returns a success message
- Blocks appear in-game at the expected coordinates
- The bot doesn't disconnect or lag out

---

### **7. BONUS: Error Handling and Build Quality**

This week's bonuses will be smaller, quicker ideas that add a lot of quality to your builds and to your projects:

1. If the build endpoint fails, have a json schematic as a backup that the bot builds:

```python
@app.route("/build", methods=["POST"])
def build():
    # Rest of the code before...

    # TODO: Call complete_schematic(data) to validate and fill in any missing blocks.
    #       If it returns None (invalid JSON), fall back to building "../schematics/example.json" from disk
    #       Hint: open the file with open(), then use json.load() to parse it

    # Rest of the code after
```

**Note:** the `example.json` mentioned in the code above will be provided in the repo, but you can change it to be a more interesting build.

2. Make sure the orientation of blocks is actually correct. The `place_block` function includes directions for blocks like stairs. It can be tricky, but try to get this to actually work.

You can test this with a house build because a roof will require stairs going in different directions!

3. Increase the amount of max tokens that Claude can output and play around with this until you find a "max" level. We will do more with this next week...

---

## **Wrapping Up**

By the end of this week, you should have:

1. Pydantic validation on Claude's JSON output before any blocks are placed
2. A `build_from_json` function that iterates the block list and issues `/setblock` commands
3. A `/build` Flask endpoint that accepts the build plan and triggers construction
4. A `utils.py` file with your Streamlit helpers cleanly separated from `main.py`
5. A **Build in Minecraft** button in Streamlit that completes the end-to-end pipeline
6. Basic error handling for truncated JSON and invalid block types

### **Next Week:**

We'll focus on build quality by improving the prompt and chunking the block output from Claude. **Hint:** Think about how you might stream block placement updates back from Flask to Streamlit!
