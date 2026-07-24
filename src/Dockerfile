# ==============================================================================
#  Image Streamlit conseiller (app.py + notifications.py + veille_prix_engine.py
#  + catalogue_engine.py). Contexte de build = racine du dépôt, mais src/ est
#  copié à plat dans /app : les modules du projet s'importent sans préfixe
#  (ex. `from db import ...` dans secrets_config.py) exactement comme
#  `streamlit run app.py` lancé depuis src/ en local.
#  Playwright + Chromium sont installés : souscription assistée, veille prix
#  et catalogue auto-alimenté fonctionnent aussi depuis ce conteneur (image
#  volontairement plus lourde, ~500 Mo de plus, décision assumée).
#  Build : docker build -f src/Dockerfile -t ia-conseil-streamlit .
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

COPY src/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY src .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
