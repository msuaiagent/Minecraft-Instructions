import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize the Anthropic client. It automatically reads ANTHROPIC_API_KEY from your .env so make sure that's there
client = anthropic.Anthropic()

# Max tokens controls how long Claude's response can be.
tokens = int(os.getenv("TOKENS", 1024))

# The system prompt sets Claude's behavior for every request.
# It includes:
#   1. The role/goal ("generate Minecraft JSON from an image")
#   2. The exact JSON schema Claude must follow
#   3. A few-shot example showing a valid build output
#   4. Hard rules Claude must obey (valid block IDs, raw JSON only, etc.)
SYSTEM_PROMPT = """You are a bot designed to generate highly detailed JSON output for building intricate structures in Minecraft from a source image, following the provided schema and examples.

**JSON Output Requirements:**
Return raw JSON with this schema:

{
    "schematic_name": string,
    "blocks": [
        {"block_type": string, "x": integer, "y": integer, "z": integer},
        ...
    ]
}

**Refer to this detailed schematic to generate a highly intricate build:**

Few shot 1:
    {
        "schematic_name": "small_house",
        "blocks": [
            {"block_type": "stone", "x": 0, "y": 0, "z": 0},
            {"block_type": "stone", "x": 1, "y": 0, "z": 0},
            {"block_type": "stone", "x": 2, "y": 0, "z": 0},
            {"block_type": "stone", "x": 0, "y": 0, "z": 1},
            {"block_type": "stone", "x": 2, "y": 0, "z": 1},
            {"block_type": "stone", "x": 0, "y": 0, "z": 2},
            {"block_type": "stone", "x": 1, "y": 0, "z": 2},
            {"block_type": "stone", "x": 2, "y": 0, "z": 2},
            {"block_type": "oak_planks", "x": 1, "y": 1, "z": 1},
            {"block_type": "oak_planks", "x": 1, "y": 2, "z": 1},
            {"block_type": "stone", "x": 0, "y": 1, "z": 0},
            {"block_type": "stone", "x": 2, "y": 1, "z": 0},
            {"block_type": "stone", "x": 0, "y": 1, "z": 2},
            {"block_type": "stone", "x": 2, "y": 1, "z": 2},
            {"block_type": "stone", "x": 0, "y": 2, "z": 0},
            {"block_type": "stone", "x": 2, "y": 2, "z": 0},
            {"block_type": "stone", "x": 0, "y": 2, "z": 2},
            {"block_type": "stone", "x": 2, "y": 2, "z": 2}
        ]
    }

**Instructions:**
    - Use only valid Minecraft block IDs (e.g., "stone_bricks", "oak_planks").
    - Determine facing directions for orientable blocks based on the bots fixed position.
    - Only return RAW JSON, no comments or markdown."""


def call_analyzer(img, img_bytes, depth_str=None):
    # Start with a base prompt. If depth data is available, we'll append it below.
    prompt = "Analyze this image and produce a Minecraft build plan in JSON."

    # Upload the image to Anthropic's Files API.
    # This is more efficient than base64-encoding large images inline,
    # and is required to use the files-api-2025-04-14 beta feature.
    image_data = client.beta.files.upload(
        file=(img.name, img_bytes.getvalue(), img.type)
    )

    # Send the uploaded image and prompt to Claude.
    # The message content has two parts:
    #   1. The image (referenced by its uploaded file ID)
    #   2. The text prompt asking Claude to produce the build plan
    response = client.beta.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=tokens,
        system=SYSTEM_PROMPT,
        betas=["files-api-2025-04-14"],  # Required to use the Files API
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "file", "file_id": image_data.id},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    # Extract the raw text from Claude's response
    json_str = response.content[0].text.strip()

    # Claude sometimes wraps its output in markdown code fences (```json ... ```)
    # even when instructed not to. Strip them out before parsing.
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]

    print(f"Claude response: {json_str}")

    # Parse the cleaned string into a Python dict and return it.
    # If parsing fails, print the error and return None so the caller can handle it.
    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        print(f"Final parse error: {e}")
        return None
