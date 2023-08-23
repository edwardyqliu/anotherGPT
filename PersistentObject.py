from Schemaful import Schemaful
from MemHandler import MemHandler,Stack
from functools import wraps
import asyncio
import inspect
from GPT import GPT
import json
class PersistentObject(Schemaful):
    '''
    Each Method has access to memhandler (ability to influence global context) and
    since each method is effectively a flow, each method will also control its local instance context Stacks.
    '''
    memhandler :  MemHandler           #reference to memhandler
    parent : int

    def __init__(self,memhandler : MemHandler,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.memhandler = memhandler
        
    def handleSchema(func):
        @wraps(func)
        async def wrapper(self,*args,**kwargs):
            assert isinstance(self,PersistentObject)
            asst = []
            try:
                if not inspect.iscoroutinefunction(func):
                    print("function",func)
                    result = func(self,*args,**kwargs)
                else:
                    print("function",func)
                    result = await func(self,*args,**kwargs)
                return result
            
            except Exception as e:
                print("init_error",e)
                schema = getattr(self,(str(func.__name__)+"Schema"))   #get funcSchema (list of possible Schemas) if func
                async def recurs(count):
                    if count > self.LIMIT:
                        raise asyncio.CancelledError
                    funct,functParam,functMsg = None,None,None
                    if schema:
                        if not (funct or functParam or functMsg):
                            message = {"role":"system",
                                            "content":"Do a function Call or ask user with the intention their response be used for the function's parameters"}
                            result = await self.gpt.functionCall(
                                message = message, 
                                masterQ = self.outputQ,
                                schemas = schema,
                                assistant = self.gpt.messageHistory + asst,
                                functioncall = "auto",  #TODO Change
                                stream = self.STREAM
                                )
                            asst.append(message)                                
                            (funct,functParam),functMsg = result.get("function",(None,None)),result

                            f = result.get("function",(None,None))
                            msg = result 
                            (funct,functParam) = f
                            if functParam and type(functParam) != dict:
                                    functParam = json.loads(functParam)

                            if not functParam and not funct:
                                functMsg = msg
                            else:
                                functMsg = None
                                asst.append({"role":"assistant","content":f"I picked {funct} {functParam}"})

                        if funct and functParam:  #function call implies execution, upon fail ask for user responses
                            funct = getattr(self,"_"+str(funct))

                            try:
                                if inspect.iscoroutine(funct):
                                    result = await funct(**functParam)
                                else:
                                    result = funct(**functParam)
                                print("success")  
                                self.gpt.messageHistory += asst                              
                                return result
                            
                            except Exception as e:
                                print("error async",e)
                                pass

                        if not functMsg:
                            message = {"role":"system",
                                        "content":f"""Your Previous Execution failed! Given the following schemas {getattr(self,(str(func.__name__)+"Schema"))}, tell the user something\n"""}
                            functMsg = await self.gpt.prompt(
                                message = message, 
                                masterQ = self.outputQ,
                                schemas = schema,
                                assistant = self.gpt.messageHistory + asst,
                                functioncall = "auto",  #TODO Change
                                stream = self.STREAM
                                )
                            asst.append(message)
                        
                        if functMsg:  # waited past all queues AND theres a function message 
                            print("Back from the dead")
                            asst.append(functMsg)
                            self.memhandler.currobj = self #<== point to self when it's your turn
                            try:
                                response = await asyncio.wait_for(self.userQ.get(),timeout = self.TIMEOUT)
                            except Exception as e:
                                print(repr(e))
                                raise asyncio.CancelledError
                            asst.append({"role":"user","content": response})
                            functMsg = None
                    
                    self.gpt.messageHistory+=asst 
                    print(funct,functParam,functMsg,response,count)
                    await recurs(count + 1)
            await recurs(0)
        return wrapper
    
    @handleSchema
    def enter(self):
        '''
        Declares what to do on initalization
        '''
        raise NotImplementedError
    
    @handleSchema
    def exit(self):
        '''
        Declares what to do when user Exits Application
        '''
        raise NotImplementedError
    
    @handleSchema
    def reset(self):
        '''
        Declares what to do if user resets Class
        '''
        raise NotImplementedError
    
    def __call__(self):
        return "Welcome to " + type(self).__name__
    
    def matchCommand(self,query : str):
        if not query.strip().startswith("-"):
            return None
        
        match query.strip().lower():
            case _:
                return "No commands for this object! \
                        To view memory commands, use +help \n \
                        Cheers!"
            
if __name__ == "__main__":
    memTest = MemHandler(cachelimit = 10, llm = GPT, P_q = asyncio.Queue(maxsize=1),U_q = asyncio.Queue(maxsize = 1),O_q = asyncio.Queue())
    obj = PersistentObject(memhandler = memTest,llm = GPT, P_q = asyncio.Queue(maxsize=1),U_q = asyncio.Queue(maxsize = 1),O_q = asyncio.Queue())
    print("test complete")
