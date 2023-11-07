
# import os
# import re
# import json
# from chromadb.utils import embedding_functions
# from app import chroma_client
# from src.individual.models import Individual

# from decimal import Decimal
# # Extend the JSONEncoder to handle Decimal type
# class DecimalEncoder(json.JSONEncoder):
#   def default(self, obj):
#     if isinstance(obj, Decimal):
#       return str(obj)
#     return json.JSONEncoder.default(self, obj)
  

# def get_collection(name: str):
#     ef = embedding_functions.DefaultEmbeddingFunction()
#     # ef = embedding_functions.OpenAIEmbeddingFunction(
#     #     api_key=os.environ.get("OPENAI_API_KEY"),
#     #     model_name="text-embedding-ada-002"
#     # )
#     return chroma_client.get_or_create_collection(name=name, embedding_function=ef)


# def populate_individuals(limit: int):

#   collection = get_collection("individual")

#   # Add individuals
#   individuals: list[Individual] = Individual.query.limit(limit).all()
#   individual_dicts = [individual.to_dict(include_company=False) for individual in individuals]

#   def clean_input(value):
#     url_pattern = r'https?://\S+'

#     dump_str = json.dumps(value, cls=DecimalEncoder, default=str)
#     cleaned_string = re.sub(url_pattern, 'null,', dump_str)
#     cleaned_string = cleaned_string.replace('"', '').replace('\\n', '').replace('\\u2022', '')

#     return cleaned_string[:6000]

#   # Clean up the data
#   individual_dicts = [
#       {
#           key: clean_input(value)
#           for key, value in d.items() if value is not None and key != 'linkedin_url' and key != 'li_public_id' and key != 'li_urn_id' and key != 'img_url' and key != 'img_expire'
#       }
#       for d in individual_dicts
#   ]

#   collection.upsert(
#     documents=[clean_input(individual_dict) for individual_dict in individual_dicts],
#     metadatas=individual_dicts,
#     ids=[str(individual_dict.get('id', -1)) for individual_dict in individual_dicts]
#   )

#   return True


# def fetch_individuals(queries: list[str], keywords: dict, amount: int):
    
#     collection = get_collection("individual")

#     results = collection.query(
#         query_texts=queries,
#         n_results=amount,
#         where=keywords,#{"first_name": "Bobby"}
#         #where_document={"$contains":"search_string"}
#     )

#     return results.get('ids')





