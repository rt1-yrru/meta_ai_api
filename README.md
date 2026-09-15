
from metaai_api import MetaAI

ai = MetaAI(cookies={
    "datr": "[your datr code ]",
    "ecto_1_sess": "[your ecto_1_sess]"
#},headed=True)
})

add headed=True ; if you want to see what happens in the browser 
simply remove it ; if you dont needed headed one 

# Chat
query=input(' enter your query/prompt to Meta ai ')
reply = ai.prompt(query)
#print(reply["message"])
## reply["message"] ; usually truncates part of the response so ; first use reply , then carve out the data you actually require 
print(reply)


# List conversations
#convs = ai.list_conversations()
#for c in convs:
#    print(c["title"])

# this lists all the  past conversation history as list 

ai.close()
