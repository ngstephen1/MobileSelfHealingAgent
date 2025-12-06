import sys
from streamlit.web import cli as stcli
sys.argv = ["streamlit","run","ui_demo/streamlit_app.py","--server.port","8502"]
stcli.main()
