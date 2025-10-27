# Retreat Manager Chatbot

This project is one step travel agent that helps the owner plan for events depending on the weather the next day. It's hardcoded to plan travels to 50 persons to keep things simple.

Agent flow:
1. Gets the city where the agent should plan for the travel agentcy (get it? :p)
2. Calls the weather api to check the weather of the city for the next day. Besides the weather we also find out the temperature and wind strength to ensure that the activity is really enjoyable during those conditions.
3. Use google search as an anchor and search for best vacation spots
4. Once the vacation activities are recommended, it's passed to the image generator to create an award winning advertising to attract people to sign up
5. It also calls the Tikkie public API to create a Tikkie that the agentcy boss to easily collect payment from the vacationers

Custom UI:
We created also a custom UI using Streamlit. It also has a very 'dumb' login page. The important thing is that it gives the username as context to the agent so messages to the agentcy employees are personalised according to who logged in.

## Example Output

Here are some sample of interactions with the travel agentcy for different countries. 

[Amsterdam](./samples/amsterdam.pdf)
[Athens](./samples/athens.pdf)
[Paris](./samples/paris.pdf)
