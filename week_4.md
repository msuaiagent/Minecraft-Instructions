# **Week 4: Build Quality & Streaming**

Welcome back! This week we're focusing on making your builds smarter and faster. You'll increase Claude's output limit, switch to a streaming + chunking approach so blocks appear in Minecraft in real time as Claude generates them, and explore bonus features like image classification and color extraction to make your prompts more contextually aware.

---

### **1. Increasing Max Tokens**

Right now you're likely capped at around 1,024–2,048 tokens, which limits how many blocks Claude can describe in a single response. A larger build like a small house can easily require 5,000–10,000 tokens of JSON output.

Token math if you're interested:

- 1 token ~ 3–4 characters
- A normal block object ~ 25-35 tokens
- 500 blocks ~ 12,500-17,500 tokens

**1.1 Update Your max_tokens**

Bump your max tokens up to around 10,000. This value can be found either in the Anthropic API call or in an environment variable:

This is a good starting point. Feel free to experiment: try 6,000, 8,000, or 12,000 and observe how build complexity scales. Be mindful that larger outputs cost more and take longer to generate.

**1.2 Why Streaming Becomes Essential**

At 10,000 tokens, waiting for the full response before placing a single block feels slow. Streaming lets you start building immediately as Claude generates output, so the bot is placing blocks while Claude is still thinking. This week's architecture change makes that happen.

---

### **2. Understanding the Shift: Structured Output vs. Streaming**

Last week, you waited for Claude's complete response, parsed the whole JSON string, then built everything at once. This week, you're switching to a **streaming + chunking** approach.

The key tradeoff to understand: **Claude currently does not support structured output and streaming together easily.** Structured output (forcing a strict JSON schema) requires waiting for the complete response. Streaming requires reading raw text token by token. So instead of asking Claude to return perfectly-formed JSON and validating the whole thing at once, you'll parse individual block objects as they stream in.

Here's what changes:

- **Before:** Get full JSON string → parse → build all at once
- **After:** Stream tokens → detect complete block objects on the fly → build each one immediately

The `call_analyzer` function in `claude_client.py` is the function we will be editing.

---

### **3. Parsing Blocks from the Stream**

Open `claude_client.py` and look at the `call_analyzer` function. The comments in the code below will help you transform your Week 2 implementation:

**pause**: I highly recommend looking at the [Anthropic docs](https://platform.claude.com/docs/en/build-with-claude/streaming) for streaming prior to making these changes. A lot of the code you see below will then be more familiar!

````python
def call_analyzer(img, img_bytes, depth_str=None):
    load_dotenv()
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    tokens = int(os.getenv("TOKENS")) # You can leave the token number lower but make sure to increase it later

    client = anthropic.Anthropic()

    prompt_path = BASE_DIR / "prompt.txt" # TODO: Copy/paste your system prompt into a prompt.txt file or leave it as a variable in this file
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    image_data = client.beta.files.upload(
        file=(img.name, img_bytes.getvalue(), img.type)
    )

    # TODO: Remove the output_format schema dict entirely from the API call because structured output is incompatible with streaming

    # TODO: Initialize two empty strings: `message` (accumulates the full response)
    #       and `buffer` (holds recently streamed text not yet parsed)

    # TODO: Replace client.beta.messages.create(...) with client.beta.messages.stream(...)
    #       as a context manager (`with ... as stream:`). Remove the output_format
    #       and structured-outputs beta flag from the call. Keep files-api-2025-04-14.
    with ...() as stream:

        # TODO: Loop over events in the stream

            # TODO: Check if event.type == "content_block_delta" and
            #       event.delta.type == "text_delta". If so, grab the new text
            #       chunk and append it to both `message` and `buffer`

                # TODO: Start a `while True:` loop to extract complete
                #       block objects from the buffer as they arrive...

                    # TODO: Use buffer.find('{"block_type"') to locate the start
                    #       of a potential block object. Break if not found (== -1)

                    # TODO: Use buffer.find("}", start) to find the closing brace.
                    #       Break if not found. This means the object isn't complete yet

                    # TODO: Slice buffer[start : end + 1] to get the candidate
                    #       JSON string and attempt json.loads() on it

                        # TODO: On success, check that all required keys are present:
                        #       "block_type", "x", "y", "z". If valid, yield this block
                        #       {"type": "block", "data": block_obj}

                        # TODO: Whether valid or not, advance the buffer past the
                        #       consumed object: buffer = buffer[end + 1:]

                        # TODO: On JSONDecodeError, advance past this opening brace
                        #       only: buffer = buffer[start + 1:] and continue

            # TODO: Check if event.type == "content_block_stop" and break.
            #       This means that the message is done

    # TODO: Strip whitespace from `message` and clean any markdown like
    #       (```json, ```) from the start and end of the string

    # TODO: Try json.loads() on the cleaned string and yield
    #       {"type": "complete", "data": data} on success

    # TODO: On JSONDecodeError, print the error and yield
    #       {"type": "error", "data": json_str} so the caller can handle it
````

**3.1 What to Notice**

- Each time a complete `{"block_type": ..., "x": ..., "y": ..., "z": ...}` object is detected, it's immediately yielded
- The buffer is trimmed as objects are consumed so that it doesn't grow unboundedly
- If a block object is cut across two streaming chunks, the parser waits for the next token to complete it
- At the end of the stream, the full accumulated message is also yielded as a `"complete"` event for display purposes

**3.2 Why This Works Without Structured Output**

You're not asking Claude to return anything other than plain text. Claude just writes JSON naturally in its response. Your parser hunts for valid block objects in that text stream regardless of whatever else Claude might output (like trailing commentary). This is more resilient than strict structured output and works seamlessly with streaming. We also included few-shot examples in the system prompt to guide Claude to just respond with JSON.

---

### **4. Wiring Streaming Builds into Streamlit**

The `main.py` loop that consumes the stream should now look like this:

```python
for result in call_analyzer(uploaded_img, img_bytes, depth_str):
    if result["type"] == "block":
        block = result["data"]
        blocks_built.append(block)

        # Incrementally update the build payload
        build_payload = {
            "schematic_name": "streaming_build",
            "blocks": blocks_built,
        }
        st.session_state.build_data = build_payload # Save the payload to the session_state so we don't have to pass it into the call_build function

        # Immediately send each block to the bot
        call_build(button=False)

        status_placeholder.text(f"Built {len(blocks_built)} blocks so far...")

    elif result["type"] == "complete":
        st.session_state.build_data = result["data"]
        status_placeholder.success(
            f"Complete! Total blocks: {len(result['data'].get('blocks', []))}"
        )

    elif result["type"] == "error":
        error_placeholder.error("Parsing error occurred. Build may be incomplete.")
```

**4.1 What "Success" Looks Like**

- You click **Analyze Image**
- Blocks start appearing in Minecraft within a few seconds even before Claude has finished generating
- The status counter increments in Streamlit as blocks are placed
- When Claude finishes, a final success message shows the total block count
- I recommend leaving in some Week 3 code: at the end, check if the session state has build_data. If it does, then display the JSON and show a button that will build the entire structure even after the chunked building

**4.2 A Note on `call_build(button=False)`**

Notice that `call_build()` is called with `button=False` during streaming. This suppresses the success toast on every single block, otherwise your UI would be flooded with messages. The `button=True` version is reserved for the manual **BUILD** button (described in the last bullet above).

---

### **5. Testing Your New Pipeline**

**5.1 Pre-Flight Checklist**

- Update `TOKENS` in your `.env`
- Restart Flask so the new token limit takes effect
- Make sure your bot is spawned and has the right permissions

**5.2 What to Test With**

After ensuring that your streamed output pipeline doesn't crash (with a smaller token size), try something slightly larger than last week such as a tower, a log cabin with a roof, or Beaumont Tower.

**5.3 Things to Watch For**

- Do blocks appear in-game while Streamlit is still streaming? (They should!)
- Does the final block count in the success message match what you see in-game?
- Are there any gaps or missing blocks that suggest the parser dropped a malformed object?

---

### **6. BONUS: Image Classification for Smarter Prompts**

Right now, your prompt is the same regardless of what image is uploaded. A more advanced approach would be to classify the image first, then choose a specialized prompt based on what's in it.

**6.1 Option A: Use Claude as the Classifier**

Make a fast, cheap preliminary call to Claude with a very low token limit just to classify the image:

**6.2 Option B: Use a Local Classifier Model**

You already have `transformers` installed from the required packages. Add an image classification pipeline:

```python
@st.cache_resource # Cache this st element so it doesn't reload every time
def load_classifier():
    return pipeline("image-classification",
                    model="google/vit-base-patch16-224")

classifier = load_classifier()
result = classifier(img)
label = result[0]["label"]  # e.g. "castle", "barn", "lighthouse"
```

**6.3 Using the Classification**

Once you have a label, load a different prompt file:

```python
prompt_map = {
    "house": "prompts/house_prompt.txt",
    "tower": "prompts/tower_prompt.txt",
    "pixel_art": "prompts/pixel_art_prompt.txt",
}
prompt_file = prompt_map.get(label, "prompts/default_prompt.txt") # default_prompt.txt can be our original prompt
```

Each specialized prompt can include structure-specific guidance. For example, the house prompt might remind Claude to use stairs for roofs and doors for entrances, while the tower prompt emphasizes vertical block stacking.

---

## **Wrapping Up**

By the end of this week, you should have:

1. A higher token limit (10,000+) enabling larger, more detailed builds
2. A streaming parser that detects and builds blocks in real time as Claude generates them
3. A clear understanding that streaming and structured output are mutually exclusive (for now) and how to work around it
4. (Bonus) Image classification that selects specialized prompts based on what's in the image

### **Coming Up:**

We'll explore prompt engineering in depth (literally). We will improve our prompt for each build by using a pre-trained model to extract depth features from the uploaded image. Any work on this week's Bonus section will help with this next implementation. **Hint:** For future prompt improvements, think about what constraints you'd give a human builder to get consistent, interesting results!
