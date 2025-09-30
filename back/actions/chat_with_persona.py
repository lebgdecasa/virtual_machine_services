# chat_with_persona.py
import os
import traceback
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
# Get the project root directory (3 levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

def setup_gemini_client():
    """Initialise et retourne le client Gemini."""
    api_key = os.environ.get("NEXT_PUBLIC_GEMINI_API_KEY")
    if not api_key:
        print("ERREUR CRITIQUE: La variable d'environnement NEXT_PUBLIC_GEMINI_API_KEY n'est pas définie.")
        # Dans un contexte API, il serait mieux de lever une exception ou de gérer ça autrement
        return None
    try:
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        print(f"Erreur lors de l'initialisation du client Gemini: {e}")
        return None

# Nouvelle fonction pour obtenir une seule réponse
def get_persona_response(system_instruction: str, history: list, user_message: str) -> str:
    """
    Obtient une seule réponse du modèle Gemini pour le chat.

    Args:
        system_instruction: Le prompt système pour le persona.
        history: L'historique de la conversation au format attendu par google-genai
                 (liste de types.Content).
        user_message: Le dernier message texte de l'utilisateur.

    Returns:
        La réponse texte de l'IA, ou un message d'erreur.
    """
    client = setup_gemini_client()
    if not client:
        return "Erreur : Le client Gemini n'a pas pu être initialisé (Vérifiez la clé API et les logs serveur)."

    # Choisir le modèle (peut être rendu configurable)
    model_name = "gemini-2.0-flash-lite" # Utiliser le nom complet du modèle

    # Construire l'historique complet pour l'appel API
    # L'historique reçu est déjà une liste de types.Content si bien géré dans api.py
    # Ajouter le nouveau message utilisateur
    current_turn = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    conversation_contents = history + [current_turn]

    # Configuration de la génération
    # NOTE: Vérifiez la documentation google-genai pour la version que vous utilisez.
    # Le 'system_instruction' pourrait devoir être passé différemment (parfois comme premier message).
    # Ici on suppose qu'il est dans la config, comme dans votre code original.
    config = types.GenerationConfig(
        # response_mime_type="text/plain", # Moins courant dans les nouvelles versions, souvent implicite pour le texte
        # Ajoutez d'autres paramètres de génération si nécessaire (temperature, top_p, etc.)
        # temperature=0.7
    )

    # Définir l'instruction système (méthode recommandée peut varier selon version/modèle)
    # Option 1: Dans la config (comme votre code original) -> Moins courant maintenant
    # config.system_instruction = [system_instruction] # Vérifiez si c'est supporté

    # Option 2: Comme partie du contenu (plus courant avec les API récentes)
    # Adaptez si 'system_instruction' doit être une string simple ou un objet Content/Part
    system_content = types.Content(role="system", parts=[types.Part.from_text(system_instruction)]) # A VERIFIER / AJUSTER


    print(f"DEBUG: Appel Gemini pour historique de {len(conversation_contents)} messages.") # Log utile
    try:
        # Utiliser la méthode non-streamée : generate_content
        # Ajustez l'appel selon comment le system_prompt est géré
        response = client.generate_content(
            model=model_name,
            # Option A: Si system_instruction est dans config
            # contents=conversation_contents,
            # config=config,
            # Option B: Si system_instruction est au début du contenu
            contents=[system_content] + conversation_contents, # Mettre le system prompt au début
            generation_config=config # Passer les autres configs ici
        )

        # Extraire la réponse texte - CELA DEPEND FORTEMENT DE LA STRUCTURE DE L'OBJET 'response'
        # Inspectez l'objet 'response' ou consultez la documentation google-genai
        # Tentatives communes :
        response_text = ""
        if response.text: # Simple accès direct (moins courant maintenant)
             response_text = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            # Accès via la structure standard des candidats
            response_text = "".join(part.text for part in response.candidates[0].content.parts)
        else:
            # Si aucune méthode ne marche, loggez la structure pour comprendre
            print(f"ERREUR: Structure de réponse Gemini inattendue : {response}")
            return "Désolé, j'ai reçu une réponse mais n'ai pas pu l'extraire."

        print(f"DEBUG: Réponse Gemini reçue : {response_text[:100]}...") # Log utile
        return response_text.strip()

    except Exception as e:
        print(f"ERREUR: Exception lors de l'appel API Gemini : {e}\n{traceback.format_exc()}")
        return f"Désolé, une erreur s'est produite en contactant l'IA : {str(e)}"


def chat_with_gemini(sys_instruction, name):
    client = setup_gemini_client()
    model = "gemini-2.0-flash-lite"

    print(f"Welcome! You are now chatting with {name} . Type 'exit' to quit.\n")

    messages = []

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            break

        # Add user message to conversation
        messages.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
        )

        config = types.GenerateContentConfig(
            response_mime_type="text/plain",
            system_instruction=[sys_instruction]
        )

        print(f"{name}:", end=" ", flush=True)

        # Stream the Gemini response
        reply_parts = []
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=messages,
            config=config,
        ):
            print(chunk.text, end="", flush=True)
            reply_parts.append(chunk.text)

        print("\n")

        # Save assistant response into the conversation
        messages.append(
            types.Content(role="model", parts=[types.Part.from_text(text="".join(reply_parts))])
        )
