# **Week 6: Deployment & Competition Prep**

Welcome to the final week! Your pipeline now generates 3D Minecraft builds from images. This week you'll wrap everything up by fixing a few architectural issues with the bot, deploying your Streamlit app and Flask server to the cloud, and preparing for the competition. Let's get to work!

---

### **1. The Deployment Problem: Serverless vs. Persistent**

Before writing any code, it's worth understanding _why_ deployment is trickier than expected.

A **serverless** platform (like Vercel) spins up a fresh container on every incoming request and shuts it back down when the request finishes. This works great for stateless APIs, but our Minecraft bot is stateful. It needs to hold an active TCP connection to the game server. If the container dies between requests, the bot disappears from the world.

This means **we cannot use Vercel** for the Flask bot service. We need a platform that runs a persistent, always-on process. Good options are:

- **Railway** — what we'll use in the examples below. Simple GitHub deploys, persistent containers, free tier available.
- **Render** — similar to Railway, slightly different config.
- **Running Flask locally** — totally valid for the competition if cloud deployment gives you trouble.

Your **Streamlit app**, on the other hand, is stateless (it just makes HTTP calls), so it deploys cleanly to **Streamlit Cloud**.

---

### **2. Cleaning Up Before Deployment**

A few housekeeping items before you push anything to the cloud.

**2.1 Add a `requirements.txt` to `bot/`**

Your root `requirements.txt` covers Streamlit dependencies, but Railway will build your bot service from the `bot/` directory. It needs its own requirements file. Create `bot/requirements.txt` with at minimum:

```
dotenv
javascript
flask
gunicorn
pydantic
```

Add any other packages your bot actually imports. If you're unsure, run `pip freeze` in your virtual environment and trim it down to just what's needed.

**2.2 Replace Hard-Coded Usernames**

Right now your bot's Minecraft username is probably hard-coded somewhere in `bot/`. Move it to a Streamlit input field so anyone running the app can enter their own username. In your Streamlit UI:

1. Add a text input for users to type their Minecraft username
2. When the user clicks the button to spawn the bot, pass the username into the call_starter function and add it as a param to the API call to your Flask server
3. Then in your Flask route, read it from the request arguments and use it in the `BuilderBot` constructor (hint: request.args.get...)

---

### **3. Fixing the Bot Disconnect Bug**

You may have noticed that if you leave the Minecraft world and the bot disconnects, the "already started" check still thinks the bot is running. Here's why: your `BOT_INSTANCE` global never gets reset to `None` when the bot disconnects.

**3.1 The Fix: A Disconnect Callback**

Most bot libraries support a callback when the bot leaves or is kicked. Use it to call a cleanup route on your own Flask server:

```python
# TODO: Start in your BuilderBot class file
def __init__(self, username, on_disconnect=None):
        # existing init code^^
        self.on_disconnect = on_disconnect  # store the callback
        self.setup_listeners()


    # TODO: Update/add a bot 'end' listener
    @On(self.bot, "end")
    def on_end(*args):
        print("Bot disconnected.")
        if self.on_disconnect:
            self.on_disconnect()  # call our Flask callback


# TODO: Update your bot spawn endpoint to define the callback
@app.route("/bot")
def bot():
    global BOT_INSTANCE
    username = request.args.get("username")

    if BOT_INSTANCE is None:
        # TODO: define an on_disconnect function with no params
        # Get the global bot instance and set it to None. Add a print statement for debugging

        # Should have the rest of this BUT add your on_disconnect param
        BOT_INSTANCE = BuilderBot(username, on_disconnect=on_disconnect)
        return jsonify({"status": "started"})

    return jsonify({"status": "already_running"})
```

**3.2 Calling It Internally**

The callback fires an internal HTTP request back to your own server. This is a clean pattern: your bot's lifecycle events communicate back to Flask without any shared mutable state across threads.

After this fix, the flow should be:

1. Bot joins → `BOT_INSTANCE` is set
2. Bot is kicked or leaves → disconnect callback fires → resets `BOT_INSTANCE`
3. Next "Start Bot" request sees a clean state and launches a fresh bot

---

### **4. Deploying the Flask Bot to Railway**

**4.1 Create a Railway Project**

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your repository and set the **root directory** to `bot/`
4. Railway will auto-detect Python and look for a `Procfile` or `requirements.txt`

**4.2 Add a `Procfile`**

In your `bot/` directory, create a file named `Procfile` (no extension):

```
web: python app.py
```

Make sure your Flask app listens on the port Railway provides:

```python
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
```

**4.3 Set Environment Variables**

In the Railway dashboard under your service → **Variables**, add any secrets your bot needs (API keys, server IPs, max tokens, etc.). Never commit these to GitHub.

**4.4 Get Your Public URL**

Once deployed, Railway gives you a URL like `https://your-bot-service.up.railway.app`. You'll need this in the next step.

> **Common Issue: 502 errors and "development server" warnings.** Flask's built-in server is not production-grade. If Railway logs warn about this, install and use `gunicorn` instead:
>
> ```
> # bot/requirements.txt
> gunicorn
> ```
>
> ```
> # Procfile
> web: gunicorn app:app --bind 0.0.0.0:$PORT
> ```

---

### **5. Deploying Streamlit to Streamlit Cloud**

**5.1 Update the Bot URL**

In your Streamlit app, you probably have something like:

```python
BOT_URL = "http://localhost:5000"
```

Change this to read from an environment variable so you can swap it without touching code. Set BOT_URL as your deployed Railway URL if you got it to work.

```python
import os
BOT_URL = os.environ.get("BOT_URL", "http://localhost:5000")
```

**5.2 Deploy to Streamlit Cloud**

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** and select your repo + branch
3. Set the **Main file path** to your `main.py` (or wherever your Streamlit entry point is)
4. Under **Advanced settings → Secrets**, add:
   ```
   BOT_URL = "https://your-bot-service.up.railway.app"
   ```
   And any other secrets (e.g., your Anthropic API key and max token values)
5. Click **Deploy**

Streamlit Cloud reads from `st.secrets` or environment variables. Make sure your app uses one of these rather than hard-coded values for any API keys.

---

### **6. Testing with Competition-Level Images**

The repo now includes a set of test images in `test_imgs/` for you to benchmark your pipeline before the competition. These are deliberately chosen to stress-test common failure modes.

Work through each image and note what breaks:

- Curvy wall: Does Claude approximate curves with diagonal blocks, or go fully flat?
- Multi-story building: Are floors distinguishable in z-depth?
- Landscape with foreground objects: Does depth estimation separate near/far correctly?
- Simple geometric shape: Baseline sanity check
- Basic house: How does your pipeline do with larger, more complex builds? You may have to increase your max tokens if larger builds aren't being finished

For each image, ask yourself: is this failure a **prompt issue** (Claude misunderstood the structure) or a **depth issue** (the depth map was wrong or unhelpful)? Check your Streamlit depth map visualizer from Week 5 to distinguish between the two. If the depth context proves to be unhelpful, find another way to communicate this info or exclude it.

Note: each of these images are a different file format. Make sure your pipeline works for more than just PNGs

---

### **7. BONUS: WebSocket Streaming for Builds**

Right now, look at what happens every time Claude yields a new block during streaming:

```python
for result in call_analyzer(...):
    if result["type"] == "block":
        blocks_built.append(block)
        call_build()  # full HTTP POST for every single block
```

Every block triggers a complete HTTP request/response cycle. This leads to lots of overhead being repeated hundreds of times in rapid succession. A WebSocket replaces all of that with a single persistent connection that stays open for the entire build. You send each block as it arrives and Flask places it immediately, with none of the per-request overhead.

**7.1 Install `flask-sock`**

```
# bot/requirements.txt
flask-sock
```

```python
# app.py
from flask_sock import Sock
sock = Sock(app)
```

**7.2 Add a WebSocket Build Route**

Replace (or sit alongside) your existing `/build` POST route with a WebSocket endpoint. The client sends blocks one at a time as JSON messages, and the server places each one immediately as it arrives:

```python
@sock.route("/build_stream")
def build_stream(ws):
    # TODO: Return early and send an error JSON message over the websocket if there is no BOT_INSTANCE

    blocks_placed = 0
    while True:
        # TODO: Receive the next message from the websocket and break if None (client disconnected)

        # TODO: Parse the message from JSON with json.loads

        # TODO: If the message type is "done", send a completion status with total blocks placed and break

        # TODO: If the message type is "block", extract the block from 'data', build it using build_from_json,
        #       increment blocks_placed, and send back a status with the current count
```

**7.3 Update Streamlit to Use the WebSocket**

Install `websocket-client` in your root `requirements.txt`, then replace the `call_build()` loop with a single persistent connection:

```python
import websocket  # pip install websocket-client

if st.button("Analyze Image"):
    buf = BytesIO()
    img.save(buf, format=img.format)
    buf.seek(0)

    status_placeholder = st.empty()

    # Open one connection for the entire build
    ws = websocket.WebSocket()
    ws.connect("ws://localhost:5000/build_stream")  # swap for Railway URL when deployed

    for result in call_analyzer(uploaded_img, buf, depth_str):
        if result["type"] == "block":
            # Send block immediately over the open connection
            ws.send(json.dumps({"type": "block", "block": result["data"]}))
            response = json.loads(ws.recv())
            status_placeholder.text(f"Built {response['count']} blocks so far...")

        elif result["type"] == "complete":
            ws.send(json.dumps({"type": "done"}))
            response = json.loads(ws.recv())
            status_placeholder.success(f"Complete! Total blocks: {response['blocks']}")

    ws.close()
```

**7.4 Why This Is Better**

Latency will be much improved and the real-time effect is much more satisfying during a demo because the build visibly grows block-by-block in Minecraft with no batching delay. Each block is placed the moment Claude yields it rather than waiting for HTTP round trips to resolve.

---

### **Wrapping Up**

By the end of this week, you should have:

1. A `requirements.txt` in `bot/` and no hard-coded usernames
2. A working bot disconnect/reconnect fix using a callback
3. Flask deployed to Railway (or running locally as a fallback)
4. Streamlit deployed to Streamlit Cloud (pointed at your Railway URL)
5. All competition test images run through your pipeline and any major issues addressed

### **Summary of AI Topics We've Covered**

Over the semester, you've built a real multi-modal AI pipeline from scratch. Here's what you learned along the way:

- **Multi-modal input** — feeding images to Claude alongside text prompts
- **Structured output** — getting Claude to return parseable JSON for block coordinates and types
- **Streamed output** — receiving and displaying tokens progressively
- **Few-shot prompting** — guiding Claude with examples to improve build quality
- **Depth estimation** — using a pre-trained neural network to recover 3D structure from a 2D image

Nice work. Go build something cool and congrats on completing the project!
