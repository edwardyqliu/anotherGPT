import streamlit as st
import aiohttp
import json
import requests
import asyncio
import pandas as pd

#python3 streamlit run /Users/eyliu/anotherGPT/anotherGPTDemo.py
#python3 streamlit run *absolute_path_of_file*

url = 'http://127.0.0.1:8000/'

if "current" not in st.session_state:
    st.session_state["current"] = ""
class Chat():
    role: str
    content : str
    
    def __init__(self,role,content):
        self.role = role
        self.content = content

class StreamHandler():
    def __init__(self,container):
        self.content = ""
        self.container = container

    async def post_json_events(self,pth : str = "", data = ""):
        async with aiohttp.ClientSession(trust_env = True) as session:
            async with session.post(url + pth, json = data) as resp:
                while True:
                    chunk = await resp.content.readline()
                    await asyncio.sleep(.03)  # artificially long delay

                    if not chunk:
                        break
                    yield chunk.decode("utf-8")

    async def get_json_events(self,pth : str = ""):
        async with aiohttp.ClientSession(trust_env = True) as session:
            async with session.get(url + pth) as resp:
                while True:
                    chunk = await resp.content.readline()
                    await asyncio.sleep(.03)  # artificially long delay

                    if not chunk:
                        break
                    yield chunk.decode("utf-8")

    async def coroutines_post(self,path : str, text_data = ""):
        print("Entered")
        dat = {"u_text":text_data}
        text = self.content
        if text:
            self.container.write(text)
        try:
            async for event in self.post_json_events(path,data = dat):
                text = text + (bit := event.split("\BR\n")[0])
                print("".join(bit), end ="",flush = True)
                self.container.write(text)
                self.content = text
                st.session_state.current = text
            return text

        except Exception as e:
            print(repr(e) ,"in coroutines post")
            pass

    async def coroutines_get(self,path : str):
        text = self.content
        if text:
            self.container.write(text)
        try:
            async for event in self.get_json_events(path):
                text = text + (bit := event.split("\BR\n")[0])
                print("".join(bit), end ="",flush = True)
                self.container.write(text)
                self.content = text
                st.session_state.current = text
            return text


        except Exception as e:
            print(repr(e))
            pass

    def gpt(self,txt):
        asyncio.run(self.coroutines_post("GPT",text_data = txt))
        
    def reply(self,txt):
        asyncio.run(self.coroutines_post("reply",text_data = txt))

if "disabled" not in st.session_state:
    st.session_state["disabled"] = False

def toggle():
    st.session_state["disabled"] = False


def getCurrObj():
    err_tab = {"0":"AYE","1":"BEE","2":"CEE"}
    rez = requests.get(url=url+'getCurrentObject').text
    print("currObj Retrieved")
    result = rez
    try:
        return json.loads(result)
    except Exception as e:
        print(repr(e))
        return err_tab

with st.sidebar:
        if st.button(type="secondary",label="refresh",disabled = st.session_state["disabled"]):
            toggle()
            st.dataframe(data = getCurrObj())
            toggle()

if "messages" not in st.session_state:
            st.session_state["messages"] = [Chat(role = "assistant",content = "How can I help today!")]

for msg in st.session_state.messages:
        st.chat_message(msg.role).markdown(msg.content)

if prompt := st.chat_input(disabled = st.session_state["disabled"],on_submit = toggle()):
    st.session_state.messages.append(Chat(role="user", content=prompt))
    st.chat_message("user").write(prompt)
    stream_handler,stream_handler2 = None,None


    if "Reply" in prompt:
        print("a")
        with st.chat_message("assistant"):
            stream_handler2 = StreamHandler(st.empty())
            stream_handler2.content = st.session_state.current
            t1 = stream_handler2.reply(prompt.split("Reply")[1])
            st.session_state.messages.append(Chat(role = "assistant",content = stream_handler2.content))

            st.session_state["disabled"] = False
            #st.experimental_rerun()

    if "Reply" not in prompt:
        print("b")
        with st.chat_message("assistant"):
            stream_handler = StreamHandler(st.empty())
            t2 = stream_handler.gpt(prompt)
            st.session_state.messages.append(Chat(role = "assistant",content = stream_handler.content))
            st.session_state["disabled"] = False
            #st.experimental_rerun()
    
