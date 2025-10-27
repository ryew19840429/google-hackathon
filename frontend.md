project-root/
├── backend/
│   ├── app.py                          # FastAPI application
│   ├── agent.py                        # Your agent definition
│   ├── weather_activities_mapping.py   # Functional script
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── app.py                          # Streamlit application
│   ├── components/
│   │   ├── __init__.py
│   │   ├── event_form.py              # Form component
│   │   └── result_display.py          # Result display component
│   ├── utils/
│   │   ├── __init__.py
│   │   └── api_client.py              # Backend API client
│   ├── requirements.txt
│   └── .env
│
└── README.md