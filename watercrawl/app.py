import os
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from utils import searxng_fun_demand

app = FastAPI()

from starlette.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: List[str]
    n: int





@app.post("/search")
async def get_top_articles(request: QueryRequest):


    try:
        query = [q.lower() for q in request.query]
        n = request.n
        top_n_results = searxng_fun_demand(query, max_links=n)

        ### uncomment from here to use graph generation

        # await generate_graph_topics_function([query])

        # topic_keywords = "_".join(query)
        # topic_kb_filename = os.path.join(TOPICS_FILE, f"{topic_keywords}.html")
        # topic_kb = KB.load_kb_from_html(topic_kb_filename)

        # graph_results = []
        # for url in top_n_results :
        #     graph_result = fetch_and_process_article(url)
        #     graph_result = generate_article_graph(url, topic_kb)
        #     graph_results.append(graph_result)

        # sorted_results = sorted(graph_results, key=lambda x: x['article'].get('score', 0), reverse=True)

        # top_n_results = sorted_results[:n]

        #### to here

        return JSONResponse(content={"results": top_n_results})

    except Exception as e:
        print(f"Error in /search: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")





if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
