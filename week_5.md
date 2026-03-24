# **Week 5: Depth Estimation & 3D Reconstruction**

Welcome back! Last week you made your pipeline faster and smarter with streaming. This week, you're tackling prompt improvements because one of the hardest challenges of this project is **translating a 2D image into a 3D Minecraft build.** Right now, Claude has to guess depth from a flat image, which may lead to builds that are 'flat.' Claude also may not be the best LLM for image and video analysis, so you could use this week to experiment with some other models. This week you'll mitigate this issue by feeding Claude an actual depth map.

---

### **1. The Core Problem: Flat Builds**

Think about what Claude sees when you upload a photo of a house. It sees colors and shapes, but has no way to know that the front porch sticks out 2 blocks toward the viewer, that the windows are recessed 1 block into the wall, or that the roof peaks 8 blocks deep front-to-back. Without depth information, Claude has to guess and fill in the gaps.

The fix is **monocular depth estimation**: feeding a single image through a pre-trained neural network that predicts how far away each pixel is. You then pass that depth information to Claude alongside the image, so it can make informed decisions about where to place blocks in the z-axis.

---

### **2. Adding a Depth Estimation Model**

You'll add the depth estimator to your existing CV pipeline, right alongside any additions or few-shot prompts you've made before this week.

**2.1 Choosing a Model**

You have two good options:

**Option A: Depth Anything V2**

- Monocular depth estimation
- Fast enough to run on CPU
- Available on Hugging Face: `LiheYoung/depth-anything-large-hf`

**Option B: MiDaS**

- Reliable and well-documented
- Slightly easier to debug
- Good default for architectural images

We'll use Depth Anything V2 in the examples below, but either works. Use this [link](https://huggingface.co/spaces/depth-anything/Depth-Anything-V2) to upload an image and see the magic of Depth Anything!

**2.2 Loading the Model**

Add this to your `main.py`. Use `st.cache_resource` so the model only loads once per session, not on every button click:

```python
from transformers import pipeline

@st.cache_resource
def load_depth_model():
    return pipeline(
        task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf"
    )

# in the main function:
depth_estimator = load_depth_model()
```

**2.3 Generating the Depth Map**

Once the user uploads an image, run it through the estimator before calling Claude:

```python
from PIL import Image
import numpy as np

# in main again once an image is uploaded:
depth = model(img)["depth"]
depth = depth.resize(
    (16, 16), Image.BILINEAR
) # turn the depth result into a 16x16 grid (downscale)
depth_np = np.array(depth)
```

The raw output is a 2D array of floats where **higher values usually mean closer to the camera**. The initial result from using the depth model on the image will give a value to each pixel of the image, so it's good to downscale a little in case the input becomes too large for Claude.

---

### **3. Normalizing Depth to Minecraft Scale**

Raw depth values are arbitrary floats. You need to map them to a meaningful Minecraft Z range. Something like 0–10 blocks deep.

```python
def normalize_depth(grid):
    """Take a grid of raw depth values and normalize each value to a float between 0 and 1"""
    grid = grid.astype("float32")

    min_val = grid.min()
    max_val = grid.max()

    if max_val > min_val:
        return (grid - min_val) / (max_val - min_val)
    else:
        return np.zeros_like(grid)


def scale_to_minecraft(normalized: np.ndarray, max_z: int = 10) -> np.ndarray:
    """Scale a [0, 1] normalized depth array to integer Minecraft Z coordinates."""
    return (normalized * max_z).astype(int)
```

Feel free to experiment with `max_z`. A value of 10 gives you reasonable depth for a building; something like a mountain landscape might warrant 20+. You could also add a field to your Streamlit UI where you input your desired depth for each build.

---

### **4. Creating a Depth String for Claude**

Picking up where we left off in the main function, where we created a numpy array out of the depth analyzation result, we're going to apply our normalization functions and convert the depth to a string that can be added to the Claude prompt.

**4.1 Applying Normalization Functions**

```python
# TODO: Normalize the raw depth array using normalize_depth()

# TODO: Scale the normalized grid to Minecraft z-coordinates (0–max_z) using scale_to_minecraft()

# TODO: Serialize the new grid to a JSON string called depth_str (this is what gets injected into the Claude prompt)

# TODO: Display the grid as formatted text in your UI for your own understanding. Each row on its own line, each depth value
#       printed and separated by spaces (hint: use st.text())
```

**4.2 Injecting Into the Prompt**

In `claude_client.py`, build the depth string and add it to your system prompt (or append it to the user message):

1. Add depth_str as an optional parameter to your call_analyzer function
2. If depth_str exists in the call, you can add the depth context to your system prompt or user message along with a helpful sentence like:
   "Use this depth grid to reason about vertical structure, height changes,
   and relative block placement as distance from the camera. The higher the value, the more blocks away that block should be placed"

---

### **6. Testing Your Depth Pipeline**

**6.1 Visualizing the Depth Map**

Before testing with Claude, verify the depth estimator is working at all. Add a debug display to Streamlit. This will provide a better visualization than the one above where we just printed the depth values at each grid space:

```python
import matplotlib.pyplot as plt
import io

if st.checkbox("Show depth map"):
    fig, ax = plt.subplots()
    ax.imshow(scaled_depth, cmap="plasma") # scaled_depth should be whatever variable you're storing your normalized and scaled grid in
    ax.set_title("Depth Map (darker = farther)")
    ax.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    st.image(buf)
```

You should see a heatmap where walls, close objects, and foreground elements are bright, and the sky or distant background is dark (or vice versa depending on the model's convention).

**6.2 What Good Depth Looks Like in Minecraft**

A well-depth-estimated build of a house could look like:

- Front steps at z = 0–1
- Front wall at z = 2–3
- Recessed windows at z = 3–4 (one block deeper than the wall)
- Interior depth visible through windows at z = 5–7
- Back wall at z = 8–10

**6.3 Common Issues**

- **All blocks still at z=0**: Check that `depth_str` is actually being included in the message sent to Claude. Print the full prompt before the API call.
- **Depth map is all one value**: The model may not have loaded correctly, or the image upload format is incompatible. Try converting to RGB explicitly: `pil_image = pil_image.convert("RGB")`.
- **Inverted depth** (foreground and background swapped): Add `.max() - depth_array` before normalizing to flip the convention.

---

### **7. BONUS: Smarter Depth Grid Representation**

The 16×16 grid approach from the basic implementation works, but it throws away a lot of spatial information. Also from my testing, it can sometimes lead to builds being a max width and height of 16 blocks. For the bonus this week, try restructuring what the depth model outputs before it reaches Claude.

**Note:** when I first did this part, I left each depth value as a float from 0-1 and adjusted the prompt until Claude understood that this was a normalized value. At first it would just build very flat structures. You could experiment with this approach, too.

**7.1 Depth Zones**
Rather than giving Claude a raw 16×16 grid of numbers, describe the depth in terms of zones. Claude responds well to natural language constraints:

```python
def describe_depth_zones(scaled_depth: np.ndarray) -> str:
    """Convert a scaled depth array into a natural language zone description."""
    # TODO: Flatten the scaled depth array to a 1D list of z-values

    # TODO: Use np.percentile to find the foreground (25th), midground (50th), and
    #       background (75th) percentile z-values and cast each to an int

    # TODO: Return a formatted string describing the three depth zones,
    #       e.g. "Foreground (closest objects): z = 0–3 blocks"
```

**7.2 Depth Clustering**

If you want to take the depth zones idea a step further, then you could use K-means clustering to describe layers of the build. Watch the following short [video](https://www.youtube.com/watch?v=4b5d3muPQmA) to learn what this clustering _means_. Next, I recommend going line-by-line through the functions below to learn what's going on and fix the function for your code.

Instead of a raw grid, cluster pixels by depth value into discrete layers, then describe each layer by its dominant color. This is much more actionable for Claude:

```python
from sklearn.cluster import KMeans

def cluster_depth_layers(
    image_array: np.ndarray,   # H x W x 3 RGB
    depth_array: np.ndarray,
    n_layers: int = 4,
    max_z: int = 1 # should match the value in scale_to_minecraft
) -> list[dict]:
    """
    Group pixels into depth layers and describe each layer
    by its dominant color and approximate block type.
    """
    h, w = depth_array.shape
    pixels = image_array.reshape(-1, 3)
    depths = depth_array.flatten()

    layers = []
    boundaries = np.linspace(0, max_z, n_layers + 1)

    for i in range(n_layers):
        z_min, z_max = boundaries[i], boundaries[i + 1]
        mask = (depths >= z_min) & (depths < z_max)
        if mask.sum() < 10: # 10 pixels isn't enough
            continue

        layer_pixels = pixels[mask]
        dominant_color = layer_pixels.mean(axis=0).astype(int)

        layers.append({
            "z_range": (int(z_min), int(z_max)),
            "pixel_count": int(mask.sum()),
            "dominant_rgb": dominant_color.tolist(),
        })

    return layers
```

Then format the layers for the prompt:

```python
def format_layers_for_prompt(layers: list[dict]) -> str:
    lines = ["Depth layers (from closest to farthest):"]
    for layer in layers:
        z0, z1 = layer["z_range"]
        r, g, b = layer["dominant_rgb"]
        lines.append(
            f"  z={z0}–{z1}: dominant color RGB({r},{g},{b}), "
            f"coverage: {layer['pixel_count']} pixels"
        )
    return "\n".join(lines)
```

**7.3 Why This Is Better**

The layered format gives Claude concrete guidance: "at z=2–4, the dominant color is a brick red, so place stone_brick or red_terracotta there." It links color directly to depth, rather than leaving Claude to infer both independently.

## **Wrapping Up**

By the end of this week, you should have:

1. A depth estimator integrated into your CV pipeline that runs on every image upload
2. A normalization function that maps raw depth values to a 0–max_z block range
3. Depth zone descriptions injected into your Claude prompt
4. A noticeably more 3D Minecraft output compared to Week 4

### **Things to Observe**

- Do builds look more 3D from a diagonal view in Minecraft? Test this out with builds that have diagonal walls or spheres.
- Does Claude place windows recessed into walls rather than flush with them?
- Are roofs or overhangs protruding outward rather than flat?

### **Coming Up:**

Next week we'll be close to wrapping up and deploying your Streamlit UI and endpoints!
