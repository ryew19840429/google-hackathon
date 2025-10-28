import os
import streamlit as st
import requests
import time
import base64 
import json 
from st_keyup import st_keyup 

# =====================================================================
# --- Configuration and Constants ---
# =====================================================================
import os
# ... other imports

# --- Configuration ---
AGENT_BASE_URL = os.environ.get("ADK_AGENT_URL", "http://localhost:8000")
# ... rest of your configuration
# AGENT_BASE_URL = os.environ.get("ADK_AGENT_URL", "http://127.0.0.1:8000")
APP_NAME = "retreat_manager"
# USER_ID is now handled dynamically via session state
TYPING_SPEED = 0.005 # Speed for the text animation
AGENT_AVATAR = "assets/travel-agent.png"
DEBUG_MODE = False 

# --- LOGIN CONFIG ---
LOGIN_ENABLED = True # Set to False to disable the login screen

# Allowed usernames and passwords (Username: Password)
ALLOWED_CREDENTIALS = {
    "raymond": "raymond",
    "alice": "secret123",
    "bob": "password456",
    "guest": "access"
} 

# =====================================================================
# --- Utility Functions ---
# =====================================================================

def get_user_id():
    """Retrieves the dynamically set user ID from session state."""
    # Use a default ID if not logged in yet, though this should only be called post-login
    return st.session_state.get("current_user_id", "guest_user") 

# =====================================================================
# --- Session Management ---
# =====================================================================

def init_session_state():
    """Initializes all necessary Streamlit session state variables."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = None 
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_payload" not in st.session_state:
        st.session_state.last_payload = "No request sent yet."
    if "initial_greeting_sent" not in st.session_state:
        st.session_state.initial_greeting_sent = False
    if "initial_greeting_text" not in st.session_state:
        st.session_state.initial_greeting_text = ""
    if "session_creation_attempted" not in st.session_state:
        st.session_state.session_creation_attempted = False
    # Login State and dynamic User ID
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = not LOGIN_ENABLED
    if "current_user_id" not in st.session_state:
        # Initial placeholder ID. Will be set on successful login.
        st.session_state.current_user_id = "guest_user"

def create_agent_session():
    """Attempts to create a new session with the agent and initiates the greeting."""
    if st.session_state.session_id is not None:
        return # Session already exists
    
    if not st.session_state.logged_in:
        return
        
    current_user_id = get_user_id()
    session_creation_url = f"{AGENT_BASE_URL}/apps/{APP_NAME}/users/{current_user_id}/sessions"

    st.session_state.session_creation_attempted = True
    try:
        response = requests.post(session_creation_url, timeout=10)
        response.raise_for_status()
        session_data = response.json()
        agent_session_id = session_data.get("id")
        
        if agent_session_id:
            st.session_state.session_id = agent_session_id
            
            # --- CHANGE APPLIED: Only show success message if DEBUG_MODE is True ---
            if DEBUG_MODE:
                st.sidebar.success(f"Agent session created for **{current_user_id}**: **{agent_session_id}**")
            # ----------------------------------------------------------------------
            
            # CRITICAL: Initiate the greeting after a successful session creation
            if len(st.session_state.messages) == 1 and st.session_state.messages[0].get("content") == "CONNECTING":
                send_initial_greeting() # This will cause a rerun
            else:
                st.rerun() # Rerun to remove the spinner if it was there
        else:
            st.error("Error: Agent did not return a session_id.")
            st.session_state.session_id = None
            
    except Exception as e:
        st.error(f"Error creating session. Is the agent running at **{AGENT_BASE_URL}**? Details: {e}")
        st.session_state.session_id = None


# =====================================================================
# --- Agent Communication & Parsing Functions ---
# =====================================================================

def parse_agent_response(run_response):
    """Parses the nested structure of the agent's run response to find text or function calls."""
    agent_response = "Agent run initiated. No explicit text or function call found."
    events = run_response if isinstance(run_response, list) else [run_response]

    for event in events:
        if isinstance(event, dict) and 'content' in event and event['content']:
            content = event['content']
            if 'parts' in content and isinstance(content['parts'], list) and content['parts']:
                part_content = content['parts'][0]
                
                if 'text' in part_content:
                    agent_response = part_content['text']
                elif 'functionCall' in part_content:
                    func = part_content['functionCall']
                    name = func.get('name', 'unknown')
                    args = func.get('args', {})
                    args_str = ", ".join([f"{k}='{v}'" for k, v in args.items()])
                    agent_response = f"**Function Call:** `{name}({args_str})`"
    return agent_response
    
def send_initial_greeting():
    """Sends a system-level prompt to force the agent to start the conversation."""
    
    current_user_id = get_user_id()
    # 1. Prepare an explicit initial user prompt to force the agent's behavior
    initial_user_prompt = f"System initialized. My name is {current_user_id}. Please begin the conversation with the mandated personalized greeting."
    
    agent_url = f"{AGENT_BASE_URL}/run"
    
    payload = {
        "appName": APP_NAME,
        "userId": current_user_id,
        "sessionId": st.session_state.session_id,
        "newMessage": {"parts": [{"text": initial_user_prompt}], "role": "user"}, 
        "streaming": False
    }
    
    # Update debug log *before* the call
    st.session_state.last_payload = json.dumps(payload, indent=2)

    # 2. Call the agent to get the greeting
    try:
        response = requests.post(agent_url, json=payload, timeout=30)
        response.raise_for_status() 
        run_response = response.json()
        agent_greeting = parse_agent_response(run_response)
        
        # 3. Save the greeting content and set the flag
        st.session_state.initial_greeting_text = agent_greeting
        # Replace the "CONNECTING" message with the placeholder for the animation loop
        if len(st.session_state.messages) == 1 and st.session_state.messages[0].get("content") == "CONNECTING":
            st.session_state.messages[0] = {"role": "agent", "content": None}
        else: # Fallback in case the message list is not as expected
            st.session_state.messages.append({"role": "agent", "content": None}) 
        st.session_state.initial_greeting_sent = True
        
        # Force a rerun to display the greeting animation
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during initial agent greeting: {e}")
        st.session_state.session_id = None # Invalidate session on failure

def stream_text_animation(response_placeholder, text_to_type, speed):
    """Generates a text-typing animation effect."""
    current_typed_text = ""
    for char in text_to_type:
        current_typed_text += char
        # Use HTML entity for non-breaking space and block cursor
        response_placeholder.markdown(current_typed_text + "&nbsp;▌") 
        time.sleep(speed) 
    # Display the final text without the cursor
    response_placeholder.markdown(text_to_type + "&nbsp;")
    return text_to_type

# =====================================================================
# --- Main Application Logic ---
# =====================================================================

def display_chat_history():
    """Renders all messages from session state, handling the initial greeting animation."""
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"], avatar=AGENT_AVATAR if message["role"] == "agent" else None):
            # Handle the special "CONNECTING" message
            if message.get("content") == "CONNECTING":
                with st.spinner("Connecting to agent..."):
                    create_agent_session()

            # Check for the initial greeting placeholder
            is_initial_greeting_placeholder = (
                message["role"] == "agent" and 
                message["content"] is None and 
                st.session_state.initial_greeting_sent
            )
            
            if is_initial_greeting_placeholder:
                response_placeholder = st.empty()
                full_response = st.session_state.initial_greeting_text
                
                # Run the typing animation
                final_text = stream_text_animation(response_placeholder, full_response, TYPING_SPEED)
                
                # Update the message history with the final text
                st.session_state.messages[i]["content"] = final_text
                st.session_state.initial_greeting_sent = False # Reset the flag
                
                # Rerun to display the final, stable chat history without the animation loop
                st.rerun() 
            else:
                # Display all normal, fully typed messages
                st.markdown(message["content"])
                
            # --- CHANGE APPLIED: Display image if it exists in the message ---
            if "image" in message and message["image"]:
                st.image(message["image"], caption="Generated Marketing Image")

def handle_user_input(prompt_input):
    """Processes user input (text and files) and sends it to the agent."""
    
    message_parts = []
    user_message_content = ""
    
    with st.chat_message("user"):
        # Process input from st.chat_input, which can include files
        if hasattr(prompt_input, 'text') and hasattr(prompt_input, 'files'):
            
            # 1. Handle Text Part
            if prompt_input.text:
                user_message_content = prompt_input.text
                st.markdown(user_message_content)
                message_parts.append({"text": prompt_input.text})
            
            # 2. Handle File Part (Image Upload)
            if prompt_input.files:
                for uploaded_file in prompt_input.files:
                    image_bytes = uploaded_file.getvalue()
                    base64_image = base64.b64encode(image_bytes).decode("utf-8")
                    
                    image_part = {
                        "inlineData": {
                            "mime_type": uploaded_file.type,
                            "data": base64_image
                        }
                    }
                    message_parts.append(image_part)
                    
                    st.image(image_bytes, caption=f"Uploaded: {uploaded_file.name}", width=200)
                    
                    # Update message content for history display
                    file_info = f" (Uploaded image: {uploaded_file.name})"
                    user_message_content += file_info if user_message_content else file_info
                    
        else: 
            # Regular text input (no file via chat_input)
            user_message_content = prompt_input
            st.markdown(user_message_content)
            message_parts.append({"text": prompt_input})

    # Append the user's message to session state
    st.session_state.messages.append({"role": "user", "content": user_message_content})
    
    # 3. Prepare Agent Interaction Payload
    agent_url = f"{AGENT_BASE_URL}/run"
    
    current_user_id = get_user_id()
    
    payload = {
        "appName": APP_NAME,
        "userId": current_user_id, 
        "sessionId": st.session_state.session_id, 
        "newMessage": {"parts": message_parts, "role": "user"},
        "streaming": False
    }
    st.session_state.last_payload = json.dumps(payload, indent=2) # Update debug log

    # 4. Get and Display Agent Response
    agent_response = "Error: Communication with agent failed."
    with st.chat_message("agent", avatar=AGENT_AVATAR):
        response_placeholder = st.empty() 
        
        with st.spinner("Thinking..."):
            try:
                # Blocking request
                response = requests.post(agent_url, json=payload, timeout=30)
                response.raise_for_status() 
                run_response = response.json()
                agent_response = parse_agent_response(run_response)
                
            except requests.exceptions.ConnectionError:
                agent_response = "Error: Could not connect to the agent API. Is it running?"
            except requests.exceptions.HTTPError as http_err:
                agent_response = f"HTTP error occurred: {http_err} - {response.text}"
            except requests.exceptions.RequestException as req_err:
                agent_response = f"An error occurred during the request: {req_err}"
            except Exception as e:
                agent_response = f"An unexpected error occurred: {e}"

        # 5. Run typing animation for the agent's full response
        final_response = stream_text_animation(response_placeholder, agent_response, TYPING_SPEED)
        
        # 6. Update the state 
        agent_message = {"role": "agent", "content": final_response}
        
        # --- CHANGE APPLIED: Check for image and add it to the message state ---
        # If the agent's response mentions the marketing image, add its path to the message object.
        if "marketing-image.png" in final_response:
            image_path = "assets/marketing-image.png"
            agent_message["image"] = image_path
        
        st.session_state.messages.append(agent_message)

    st.rerun()
    
# =====================================================================
# --- Login Function ---
# =====================================================================

def login_form():
    """Displays the login form and handles the authentication logic."""
    
    st.image("assets/banner.png")
    
    with st.form("login_form"):
        st.markdown("Enter your credentials to access the chat application.")
        
        username = st_keyup("Username", key="username_input")
        password = st.text_input("Password", type="password", key="password_input")
        
        login_pressed = st.form_submit_button("Log In") or st.session_state.get('username_input_return', False)
        
        if login_pressed:
            
            # Check credentials against the ALLOWED_CREDENTIALS dictionary
            if username in ALLOWED_CREDENTIALS and ALLOWED_CREDENTIALS[username] == password:
                
                st.session_state.logged_in = True
                # Store the successful username in session state for dynamic session creation
                st.session_state.current_user_id = username
                
                # Reruns immediately to load the main app (no success message shown)
                st.rerun() 
            else:
                st.error("Invalid Username or Password")
                
    st.stop() # Stop execution of the rest of the app until logged in

# =====================================================================
# --- Main Streamlit Function ---
# =====================================================================

def main():
    """The main entry point for the Streamlit application."""
    st.set_option("client.toolbarMode", "minimal")
    # Set page configuration
    st.set_page_config(
        page_title="My Travel Agent", 
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    init_session_state()

    # --- LOGIN CHECK ---
    if LOGIN_ENABLED and not st.session_state.logged_in:
        login_form()
        return
        
    # --- Main App Logic (Runs only if logged_in is True or LOGIN_ENABLED is False) ---
    
    st.title(f"I Love Travel Agentcy") 
    
    # Attempt to create session only if not already created or attempted
    if st.session_state.session_id is None and not st.session_state.session_creation_attempted:
        # Add a placeholder message to trigger the connection process in display_chat_history
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "agent", "content": "CONNECTING"})


    # --- Debug Sidebar Display ---
    if DEBUG_MODE:
        with st.sidebar:
            st.markdown("---")
            st.subheader(f"User ID: {get_user_id()}") 
            st.subheader("ADK Run Payload (Debug)")
            st.code(st.session_state.last_payload, language="json")
            st.markdown("---")

    # --- Display Chat History ---
    display_chat_history()
    
    # --- Main Chat Input Loop ---
    
    prompt_input = st.chat_input(
        "Type something to help with your travel agent business", 
        disabled=st.session_state.session_id is None, 
        accept_file=True
    )
    
    if prompt_input:
        handle_user_input(prompt_input)


if __name__ == "__main__":
    main()