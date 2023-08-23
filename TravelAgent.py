from BaseClient import Base
from PersistentObject import PersistentObject
from MemHandler import MemHandler

#used for packages
import pandas as pd
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('sentence-transformers/multi-qa-mpnet-base-cos-v1')

class TravelAgent(Base):    #After declaring / Overriding Base client, declare custom objects and add starting state
    def __init__(self,stream):
        super().__init__(stream=stream)
        self.base = [{"role":"system","content":"You are a prototype human assistant that'll use function calling and your AI intellect to help the user achieve tasks. You have all the tools to your disposal."}]
        self.memhandler = MemHandler(cachelimit = 100,**self.config)  #stores context
        #create Weaviate Object (happens to be the source)
        self.weaviateDB = Database(memhandler = self.memhandler, **self.config)
        #put Weaviate Object into memhandler and give it its id
        self.memhandler.put(self.weaviateDB)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#   
class Classifier(PersistentObject):
    nonGPTContext = {"type":"Classifier","content":"Welcome to Classifier"}
    def __init__(self, data, **kwargs):
        super().__init__(**kwargs)
        self.config = kwargs
        self.data = data
        self.nonGPTContext = self.data
    
    def getFunctionSchemas(self) -> []:
        return []

    #Do Decision Tree Stuff here...

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#    
class Database(PersistentObject):
    nonGPTContext = {"type":"WeaviateDB","content":"Welcome to Weaviate DB"}
    df_attraction = pd.read_csv("travelAgentDemoData/attractions.csv").fillna("").T
    df_guides = pd.read_csv("travelAgentDemoData/guides.csv").fillna("")
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = kwargs    #pass on to future objects
        self.nonGPTContext = {"type":"Database","content":"Welcome to Database"}

    permissionSchema = []

    @PersistentObject.handleSchema
    def permission(self,choice = None):
        assert choice != None
        self.allowed =  choice
    def _permission(self,choice = None):
        assert choice != None
        self.allowed =  choice
    
    attractionOrGuideSchema = [
        {
        "name":"attractionOrGuide",
        "description": "You don't have to function call if you don't know. Determines if the user is asking about attractions or guides.",
        "parameters":{
            "type":"object",
            "properties":{
                "choice":{
                    "type":"string",
                    "description": "Is the user asking about attractions or guides?",
                    "enum":["Attractions","Guides"]
                }
            }
        },
        "required":["choice"]
        }
    ]
    @PersistentObject.handleSchema
    def attractionOrGuide(self,choice = None):
        print("Entered attraction")
        assert type(choice) == str
        self.choice = choice
    def _attractionOrGuide(self,choice = None):
        assert type(choice) == str
        self.choice = choice
    
    def _similarity(goal_text, sample_texts : list):
        #Encode query and documents
        sample_text_emb = model.encode(sample_texts)
        goal_text_emb = model.encode(goal_text)

        #Compute dot score between query and all document embeddings
        scores = util.cos_sim(goal_text_emb, sample_text_emb).cpu().tolist()[0]
        #Combine docs & scores
        text_score_pairs = list(zip(sample_texts, scores))
        #Sort by decreasing score
        text_score_pairs = sorted(text_score_pairs, key = lambda x: x[1], reverse=True)
        max_score = text_score_pairs[0][1]
        return max_score, text_score_pairs
    
    enterSchema = [
        {
        "name":"enter",
        "description": "Search the Database",
        "parameters":{
            "type":"object",
            "properties":{
            }
        }
        }
    ]
    @PersistentObject.handleSchema
    async def enter(self):
        print("entered")
        stack = []
        #queries user which one? 
        await self.attractionOrGuide()
        if self.choice == "Guides":
            self.nonGPTContext = self.df_guides
            self.memhandler.currobj = self
        elif self.choice == "Attractions":
            #seek permission before put, and put Classifier Obj
            msg = "Add Classifier to Stack"
            self.permissionSchema = [{
                "name":"permission",
                "description": f"STOP! DO NOT FUNCTION CALL BEFORE FIRST ASKING FOR PERMISSION! Please Ask User before you respond, for permission to {msg}.",
                "parameters":{
                    "type":"object",
                    "properties":{
                        "choice":{
                            "type":"boolean",
                            "description": "Does the user wish to proceed? ",
                        }
                    }
                },
            }]
            await self.permission()
            if self.allowed:
                id = self.memhandler.put(Classifier(self.df_attraction,**self.config))
                stack.append(id)
            else:
                pass

        self.allowed = None
        self.choice = None
        print("exited")
 
    
    def exit(self): 
        #should never exit. should never be called
        return
    
    def reset(self):
        #replace self with instance
        self.__init__(self,self.config)
    
    def getFunctionSchemas(self) -> list:
        return self.enterSchema
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
if __name__ == "__main__":
    x = TravelAgent()
    print("Test Complete")