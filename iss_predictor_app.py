# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import time
import numpy as np # Import de NumPy pour les opérations vectorielles
import random 
from geopy.geocoders import Nominatim 
import plotly.express as px
import plotly.graph_objects as px_go
import math

# --- FONCTIONS LOCALES POUR LES BOUTONS ---
def generate_pdf():
    st.info("📄 PDF généré (simulation locale).")

def send_email_with_pdf(email):
    st.info(f"✉️ Email simulé envoyé à {email} (local).")

def add_to_calendar(date, time):
    st.info(f"📅 Créneau simulé ajouté : {date} à {time} (local).")

def get_best_available_slot():
    from datetime import datetime
    return datetime.now()


# --- CONFIGURATION ET CONSTANTES ---


# Constantes d'API et de Géolocalisation
ISS_PASS_API_URL = "http://api.open-notify.org/iss-pass.json"
DEFAULT_LAT = 48.8566  # Paris
DEFAULT_LON = 2.3522   # Paris
MAX_PASSES = 100       # Nombre de passages à demander (Open-Notify max 100, soit environ 10-15 jours)

# Constantes de Scoring pour la classification des passages
SCORE_VISIBILITY_OPTIMAL = 10
SCORE_WEATHER_DEGAGE = 5  # Score augmenté pour donner plus de poids à la météo idéale
SCORE_WEATHER_PEU_NUAGEUX = 1

# Initialisation du service de géocodage Nominatim (utilisé pour geopy)
# Utiliser un agent utilisateur unique est une bonne pratique
geolocator = Nominatim(user_agent="iss_predictor_pro_app")

st.set_page_config(
    page_title="ISS Predictor Pro",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FONCTIONS UTILITAIRES ET LOGIQUE MÉTIER ---

def geocode_address(address):
    """
    Tente d'obtenir les coordonnées précises pour une adresse via geopy (Nominatim).
    """
    if not address or not address.strip():
        # Si l'adresse est vide, retourner les coordonnées par défaut
        return DEFAULT_LAT, DEFAULT_LON, "Localisation par défaut (Paris)", True

    try:
        location = geolocator.geocode(address, timeout=10)
        
        if location:
            return location.latitude, location.longitude, location.address, True
        else:
            # Utilisation de f-string pour une meilleure lisibilité
            st.warning(f"Impossible de géocoder l'adresse '{address}'. Utilisation de la localisation par défaut.")
            return DEFAULT_LAT, DEFAULT_LON, f"Géocodage échoué pour: '{address}'. Par défaut (Paris).", False
            
    except Exception as e:
        # Erreur générale de connexion ou autre
        st.error(f"Erreur de connexion au service de géocodage : {e}. Utilisation de la localisation par défaut.")
        return DEFAULT_LAT, DEFAULT_LON, f"Erreur géocodage. Par défaut (Paris).", False


def mock_fetch_iss_passes(lat, lon, num_passes=MAX_PASSES):
    """
    Génère des données de passage synthétiques pour le test lorsque l'API est en panne.
    """
    mock_data = []
    current_timestamp = int(time.time())
    
    for _ in range(num_passes):
        # Intervalle basé sur le cycle orbital (environ 90 minutes = 5400 secondes)
        # Ajout d'une plage plus réaliste pour la prochaine apparition
        interval = 5400 + random.randint(1800, 7200) # Entre 90min et 3.5h d'intervalle
        current_timestamp += interval
        
        # Simulation d'une distribution de durée
        duration = random.choice(
            [random.randint(100, 300) for _ in range(8)] + 
            [random.randint(400, 600) for _ in range(2)]
        )
        
        mock_data.append({
            'risetime': current_timestamp,
            'duration': duration
        })
    return mock_data

@st.cache_data(ttl=600) # Mise en cache pour 10 minutes (performant)
def fetch_iss_passes(lat, lon):
    """
    Appelle l'API Open-Notify pour obtenir les heures de passage de l'ISS (avec failover).
    Retourne les données et un message de statut propre.
    """
    params = {
        'lat': lat,
        'lon': lon,
        'n': MAX_PASSES
    }
    
    try:
        response = requests.get(ISS_PASS_API_URL, params=params, timeout=10)
        
        if response.status_code != 200:
             status_msg = f"API ISS : Échec HTTP {response.status_code}. Bascule sur données simulées."
             return mock_fetch_iss_passes(lat, lon), status_msg 
        
        data = response.json()
        
        if data.get('message') == 'success':
            return data.get('response', []), "API ISS : Connexion réussie."
        else:
            status_msg = f"API ISS : Message d'échec interne ({data.get('reason', 'Inconnu')}). Bascule sur données simulées."
            return mock_fetch_iss_passes(lat, lon), status_msg
            
    except requests.exceptions.RequestException:
        status_msg = "API ISS : Échec de connexion/Timeout. Bascule sur données simulées."
        return mock_fetch_iss_passes(lat, lon), status_msg 

def get_mock_weather(date_time):
    """
    FONCTION DE SIMULATION MÉTÉO. Simule une probabilité de ciel dégagé basée sur l'heure.
    Simplifié pour ne prendre que l'heure pour l'efficacité.
    """
    days_in_future = (date_time.date() - datetime.now().date()).days
    
    # Plus on est loin dans le futur, plus la prévision est incertaine
    if days_in_future > 15:
        base_p = [0.1, 0.2, 0.7] # Très incertain
    else:
        # Heures optimales pour l'observation visuelle (Aube/Crépuscule)
        hour = date_time.hour
        if (5 <= hour <= 7) or (19 <= hour <= 21):
            base_p = [0.7, 0.2, 0.1] # Forte chance de Dégagé
        else:
            base_p = [0.25, 0.35, 0.4] # Distribution plus uniforme

    return np.random.choice(["Ciel Dégagé", "Peu Nuageux", "Couvert", "Pluvieux"],p=[0.5, 0.2, 0.2, 0.1])


def get_sol_ciel_category(risetime):
    """
    Détermine la catégorie Sol/Ciel (moment de la journée) et la visibilité ISS.
    """
    hour = risetime.hour
    
    # Visibilité optimale (ISS éclairée par le Soleil, observateur dans la nuit/crépuscule)
    if 5 <= hour <= 7:
        category = 'Aube'
        visibility = 'Optimale'
    elif 19 <= hour <= 21:
        category = 'Crépuscule'
        visibility = 'Optimale'
    elif 7 < hour < 19:
        category = 'Jour'
        visibility = 'Faible' # Trop de lumière solaire
    else: # 21h à 5h
        category = 'Nuit Profonde'
        visibility = 'Faible' # L'ISS est dans l'ombre de la Terre
        
    return category, visibility


# Dictionnaire de Mapping pour une résolution plus rapide des symboles
SYMBOL_MAP = {
    'Aube': "🌅 Aube", 
    'Crépuscule': "🌇 Crépuscule", 
    'Jour': "☀️ Jour",
    'Nuit Profonde': "🌑 Nuit Profonde",
    'Ciel Dégagé': "✨ Dégagé", 
    'Peu Nuageux': "☁️ Peu Nuageux",
    'Couvert': "🌫️ Couvert",
    'Pluvieux': "🌧️ Pluvieux",
    'Optimale': "🟢 Optimale",
    'Faible': "🔴 Faible"
}

def get_symbol_display(status):
    """ Fonction de lookup unifiée pour les symboles """
    return SYMBOL_MAP.get(status, status)

def process_passes(raw_passes, preferred_time_slot, min_duration_sec, start_date):
    """
    Traite les données brutes, applique les filtres, ajoute les analyses et prépare les DataFrames finaux.
    """
    
    if not raw_passes:
        data_span = "(Aucune donnée brute)"
        return pd.DataFrame(), pd.DataFrame(), data_span, pd.DataFrame()

    # 1. Conversion en DataFrame et ajout des colonnes de base
    data = []
    for p in raw_passes:
        # Utilisation d'un bloc try/except minimal pour ignorer les entrées mal formées
        try:
            risetime = datetime.fromtimestamp(p['risetime'])
            duration = p['duration']
            
            # Application des fonctions utilitaires (moins coûteux que les opérations DF)
            time_of_day_category, visibility_status = get_sol_ciel_category(risetime)
            weather_status = get_mock_weather(risetime)
            
            data.append({
                'Date Heure du Passage (UTC)': risetime,
                'Durée (Secondes)': duration,
                'Moment Sol/Ciel': time_of_day_category, 
                'Visibilité ISS Estimée': visibility_status, 
                'Visibilité Météo (Simulée)': weather_status
            })
        except (TypeError, ValueError):
            continue
            
    df = pd.DataFrame(data)
    
    # Calcule la plage de données brutes
    min_date = df['Date Heure du Passage (UTC)'].min().strftime('%d %b')
    max_date = df['Date Heure du Passage (UTC)'].max().strftime('%d %b')
    full_data_span = f"(Du {min_date} au {max_date})"
    
    # 2. APPLICATION DES FILTRES (Date, Durée, Créneau Horaire)
    
    # Filtre de Date: utilisation de datetime.combine pour comparer correctement
    df_filtered = df[df['Date Heure du Passage (UTC)'] >= datetime.combine(start_date, datetime.min.time())].copy()
    
    # Filtre de Durée
    df_filtered = df_filtered[df_filtered['Durée (Secondes)'] >= min_duration_sec].copy()

    # Filtre de Créneau Horaire
    if preferred_time_slot != "Tous":
        if preferred_time_slot == "Faible Visibilité":
            # Si Faible Visibilité est sélectionné, inclure Jour et Nuit Profonde
            df_filtered = df_filtered[df_filtered['Moment Sol/Ciel'].isin(['Jour', 'Nuit Profonde'])].copy()
        else:
            # Sinon, filtrer sur le créneau précis
            df_filtered = df_filtered[df_filtered['Moment Sol/Ciel'] == preferred_time_slot].copy()

    # 3. SÉLECTION POUR LE CLASSEMENT (Passages Observables Potentiels)
    df_filtered_for_scoring = df_filtered[
        df_filtered['Visibilité Météo (Simulée)'].isin(["Ciel Dégagé", "Peu Nuageux"])
    ].copy()

    
    # 4. LOGIQUE DE CLASSEMENT (Score Composite) - **OPTIMISATION VECTORIELLE**
    df_sorted = pd.DataFrame()
    
    if not df_filtered_for_scoring.empty:
        
        # --- Vectorisation de Score_Visibilite (np.where) ---
        df_filtered_for_scoring['Score_Visibilite'] = np.where(
            df_filtered_for_scoring['Visibilité ISS Estimée'].str.contains('Optimale'),
            SCORE_VISIBILITY_OPTIMAL,
            0
        )
        
        # --- Vectorisation de Score_Meteo (np.select pour les conditions multiples) ---
        conditions = [
            df_filtered_for_scoring['Visibilité Météo (Simulée)'].str.contains('Ciel Dégagé'),
            df_filtered_for_scoring['Visibilité Météo (Simulée)'].str.contains('Peu Nuageux'),
            df_filtered_for_scoring['Visibilité Météo (Simulée)'].str.contains('Pluvieux')  # <-- ajout
        ]
        choices = [
            SCORE_WEATHER_DEGAGE,
            SCORE_WEATHER_PEU_NUAGEUX,
            0  # Score pour Pluvieux, peut être 0 ou négatif
        ]
        df_filtered_for_scoring['Score_Meteo'] = np.select(conditions, choices, default=0)

        # Calcul du score total et tri
        df_filtered_for_scoring['Total_Score'] = df_filtered_for_scoring['Score_Visibilite'] + df_filtered_for_scoring['Score_Meteo']
        
        # Tri: Score Total (combiné) > Durée
        df_sorted = df_filtered_for_scoring.sort_values(
            by=['Total_Score', 'Durée (Secondes)'], 
            ascending=[False, False]
        ).reset_index(drop=True).drop(columns=['Total_Score', 'Score_Visibilite', 'Score_Meteo'])

    # 5. PRÉPARATION POUR L'AFFICHAGE (Ajout des symboles et formatage des colonnes)
    df_observable_display = pd.DataFrame()
    if not df_sorted.empty:
        df_observable_display = df_sorted.copy()
        
        # Utilisation de la fonction de lookup unifiée
        df_observable_display['Moment/Ciel'] = df_observable_display['Moment Sol/Ciel'].apply(get_symbol_display)
        df_observable_display['Visibilité ISS'] = df_observable_display['Visibilité ISS Estimée'].apply(get_symbol_display)
        df_observable_display['Météo Sim.'] = df_observable_display['Visibilité Météo (Simulée)'].apply(get_symbol_display)
        
        # Formatage de la durée
        df_observable_display['Durée (min:sec)'] = df_observable_display['Durée (Secondes)'].apply(
            lambda x: f"{x // 60:02d}:{x % 60:02d}"
        )
        
        # Sélection et renommage des colonnes pour la table finale (ordre de lecture optimisé)
        df_observable_display = df_observable_display[[
            'Date Heure du Passage (UTC)', 
            'Durée (min:sec)', 
            'Visibilité ISS', 
            'Moment/Ciel', 
            'Météo Sim.'
        ]].rename(columns={
            'Date Heure du Passage (UTC)': 'Date et Heure (UTC)',
            'Durée (min:sec)': 'Durée'
        })
        
        # Réindexer pour commencer à 1
        df_observable_display.index = np.arange(1, len(df_observable_display) + 1)
        df_observable_display.index.name = 'Rang'


    # 6. Génération du Résumé
    summary = (
        f"**Passages Bruts {full_data_span}:** {len(df)}. "
        f"**Passages Filtrés (Date/Durée/Heure):** {len(df_filtered)}. "
        f"**Passages Observables Classés (Ciel Dégagé/Peu Nuageux):** {len(df_sorted)}."
    )

    # Retourne df_sorted pour le graphique et df_observable_display pour les tableaux
    return df, df_observable_display, summary, df_sorted


def simulate_iss_trajectory(observer_lat, observer_lon, pass_duration_sec):
    """
    Simule une trajectoire ISS plausible (un arc) au-dessus de la zone pour la visualisation.
    """
    num_points = 20
    trajectory_points = []
    
    # Détermination aléatoire de la direction du passage
    lat_diff_direction = 1 if random.random() > 0.5 else -1
    lon_diff_direction = 1 if random.random() > 0.5 else -1
    
    # Création d'un arc aléatoire
    arc_span = 10 
    start_lat = observer_lat + lat_diff_direction * (arc_span / 2) * random.uniform(0.1, 0.4)
    end_lat = observer_lat - lat_diff_direction * (arc_span / 2) * random.uniform(0.1, 0.4)
    start_lon = observer_lon + lon_diff_direction * (arc_span / 2) * random.uniform(0.4, 0.8)
    end_lon = observer_lon - lon_diff_direction * (arc_span / 2) * random.uniform(0.4, 0.8)

    for i in range(num_points):
        t = i / (num_points - 1)
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        
        # Courbure au milieu de l'arc
        mid_point_adjustment = 0.5 - abs(t - 0.5)
        
        lat_adjusted = lat + (observer_lat - lat) * mid_point_adjustment * 0.5
        lon_adjusted = lon + (observer_lon - lon) * mid_point_adjustment * 0.5
        
        trajectory_points.append({
            'lat': lat_adjusted,
            'lon': lon_adjusted,
            'Type': 'Trajectoire ISS',
            'Info': f'Passage Simulé (Durée: {pass_duration_sec // 60}m {pass_duration_sec % 60}s)'
        })
        
    return pd.DataFrame(trajectory_points)

# --- INTERFACE UTILISATEUR (FRONTEND) ---

# Configuration commune pour les colonnes de la table Streamlit (EMOJIS RENDUS CORRECTEMENT)
DATAFRAME_COLUMN_CONFIG = {
    "Date et Heure (UTC)": st.column_config.DatetimeColumn(
        "Date et Heure (UTC)",
        format="D MMM YY, HH:mm:ss"
    ),
    "Durée": st.column_config.TextColumn(
        "Durée (min:sec)"
    ),
    "Visibilité ISS": st.column_config.TextColumn(
        "Visibilité ISS (Critère Sol/Ciel)",
        help="Est-ce que l'ISS est éclairée et le sol sombre ? Optimale (🟢) ou Faible (🔴)."
    ),
    "Moment/Ciel": st.column_config.TextColumn(
        "Moment de la Journée",
        help="Aube/Crépuscule : Visibilité ISS Optimale. Jour/Nuit Profonde : Visibilité Faible."
    ),
    "Météo Sim.": st.column_config.TextColumn(
        "Météo Sim. (Ciel)",
        help="Simulation de la Condition du Ciel : Dégagé (✨), Peu Nuageux (☁️), Couvert (🌫️), Pluvieux (🌧️)."
    )
}


def process_all_data():
    """
    Fonction centrale pour récupérer, traiter et stocker les résultats dans session_state.
    Ajout du statut de l'API pour un affichage propre.
    """
    # Récupération des paramètres à partir de la session
    lat = st.session_state['lat']
    lon = st.session_state['lon']
    time_slot = st.session_state.get('preferred_time_slot_input', 'Tous')
    min_duration = st.session_state.get('min_duration_input', 30)
    start_date = st.session_state.get('start_date_input', datetime.now().date())
    
    # 1. Fetch data (cachable) - Récupère aussi le statut
    raw_passes_data, api_status_message = fetch_iss_passes(lat, lon)
    
    # 2. Process data (heavy lifting)
    df_raw, df_observable_display, summary, df_sorted = process_passes(
        raw_passes_data, 
        time_slot, 
        min_duration,
        start_date
    )
    
    # 3. Store results in session state for reuse
    st.session_state['df_observable_display'] = df_observable_display
    st.session_state['df_sorted'] = df_sorted
    st.session_state['summary'] = summary
    st.session_state['total_observable_count'] = len(df_observable_display)
    st.session_state['api_status_message'] = api_status_message # Stocke le statut de la connexion

def main():
    st.title("🛰️ ISS Predictor Pro: L'espace à portée de vue !") # 
      
    # --- NOUVELLE ACCROCHE PROFESSIONNELLE ---
    st.markdown("""
        **Bienvenue sur ISS Predictor Pro, votre outil professionnel de prévision des passages optimaux de l'ISS.**  
          
        **Définissez vos préférences de localisation et d'horaires.**  
        L'application identifie les passages les plus favorables de la Station Spatiale Internationale près de votre position, sur ses 100 prochaines révolutions officielles.  
        ISS Predictor Pro optimise l'observation de l'ISS en tenant compte des meilleures conditions temporelles et météorologiques,  et facilite les échanges radio ou satellites dans le cadre de programmes spatiaux, de recherche ou scolaires.
        
               
    """)
    st.divider() # Séparation de l'accroche et de la configuration
    
    
    # Initialisation des variables de session
    if 'lat' not in st.session_state:
        st.session_state['lat'] = DEFAULT_LAT
        st.session_state['lon'] = DEFAULT_LON
        st.session_state['display_location'] = "Paris, France"
        st.session_state['geocoding_success'] = True 
        st.session_state['address_input'] = ""
        st.session_state['is_processed'] = False 
        st.session_state['api_status_message'] = "Non traité"



    # --- ENCADREMENT MODERNE 1: Configuration et Carte ---
    st.subheader("⚙️ Définition des paramètres de localisation et de filtrage")
    with st.container(border=True):
        col_map, col_controls = st.columns([1, 1])
        
        # --- Section Contrôles ---
        with col_controls:
            st.subheader("Localisation de l'observateur")

            # 1️⃣ Géolocalisation automatique au chargement (approximative)
            if 'lat' not in st.session_state or 'lon' not in st.session_state:
                try:
                    import streamlit_js_eval
                    user_location = streamlit_js_eval.streamlit_js_eval(
                        js_expressions="navigator.geolocation.getCurrentPosition(pos => [pos.coords.latitude, pos.coords.longitude])",
                        key="geo",
                        silent_errors=True
                    )
                    if user_location and isinstance(user_location, list) and len(user_location) == 2:
                        st.session_state['lat'] = user_location[0]
                        st.session_state['lon'] = user_location[1]
                        _, _, display_address, _ = geocode_address(f"{st.session_state['lat']},{st.session_state['lon']}")
                        st.session_state['display_location'] = display_address
                    else:
                        st.session_state['lat'] = DEFAULT_LAT
                        st.session_state['lon'] = DEFAULT_LON
                        st.session_state['display_location'] = "Paris, France"
                except Exception:
                    st.session_state['lat'] = DEFAULT_LAT
                    st.session_state['lon'] = DEFAULT_LON
                    st.session_state['display_location'] = "Paris, France"

            # 2️⃣ Saisie de l'adresse
            address_input_value = st.text_input(
                "Entrez une ville, pays, ou adresse (Géocodage réel via geopy)",
                value=st.session_state.get('address_input', ''),
                placeholder="Ex: Japon, Tour Eiffel, New York, 5e avenue...",
                key="address_input"
            )

            # 3️⃣ Reverse géocoding automatique si l'utilisateur saisit un lieu
            if address_input_value.strip():
                resolved_lat, resolved_lon, display_location, geocoding_success = geocode_address(address_input_value)
                # Mise à jour automatique dans session_state
                # Mise à jour safe des coordonnées manuelles
                # Mise à jour safe après initialisation
                if st.session_state.get('lat_manual_initialized', False):
                    st.session_state['lat_manual_input'] = resolved_lat

                if st.session_state.get('lon_manual_initialized', False):
                    st.session_state['lon_manual_input'] = resolved_lon

                # Coordonnées utilisées pour traitement et affichage
                st.session_state['lat'] = resolved_lat
                st.session_state['lon'] = resolved_lon
                st.session_state['display_location'] = display_location
                st.session_state['geocoding_success'] = geocoding_success

                # Déclenchement du traitement + activation touche Entrée
                st.session_state['is_processed'] = True
                st.session_state['is_processed'] = True
                
            # 4️⃣ Coordonnées GPS manuelles
            # --- INITIALISATION DES COORDONNÉES (évite -90 / -180 par défaut) ---
            if 'lat' not in st.session_state or 'lon' not in st.session_state:
                # Exemple de valeur par défaut : Paris
                st.session_state['lat'] = 48.8566
                st.session_state['lon'] = 2.3522

            # --- INPUT UTILISATEUR ---
            # --- Initialisation des flags pour éviter les warnings Streamlit ---
            if 'lat_manual_input' not in st.session_state:
                st.session_state['lat_manual_input'] = st.session_state.get('lat', DEFAULT_LAT)

            if 'lon_manual_input' not in st.session_state:
                st.session_state['lon_manual_input'] = st.session_state.get('lon', DEFAULT_LON)

            # --- Reverse geocoding automatique si l'utilisateur saisit un lieu ---
            address_input_value = st.session_state.get('address_input', '').strip()
            if address_input_value:
                resolved_lat, resolved_lon, display_location, geocoding_success = geocode_address(address_input_value)

                # Mise à jour safe pour le reverse geocoding
                if st.session_state.get('lat_manual_input') != resolved_lat:
                    st.session_state['lat_manual_input'] = resolved_lat
                if st.session_state.get('lon_manual_input') != resolved_lon:
                    st.session_state['lon_manual_input'] = resolved_lon

                # Coordonnées utilisées pour traitement et affichage
                st.session_state['lat'] = resolved_lat
                st.session_state['lon'] = resolved_lon
                st.session_state['display_location'] = display_location
                st.session_state['geocoding_success'] = geocoding_success
                st.session_state['is_processed'] = True

            # --- Widgets Number Input pour Latitude / Longitude ---
            lat_manual = st.number_input(
                "Latitude",
                format="%.4f",
                min_value=-90.0,
                max_value=90.0,
                step=0.0001,
                key="lat_manual_input",
                disabled=bool(address_input_value)
            )
            lon_manual = st.number_input(
                "Longitude",
                format="%.4f",
                min_value=-180.0,
                max_value=180.0,
                step=0.0001,
                key="lon_manual_input",
                disabled=bool(address_input_value)
            )
            if 'lat_manual_input' not in st.session_state:
                st.session_state['lat_manual_input'] = st.session_state['lat']

            if 'lon_manual_input' not in st.session_state:
                st.session_state['lon_manual_input'] = st.session_state['lon']
    
            st.divider()

            # 3. INPUTS DE FILTRAGE
            with st.expander("2. Définir les critères d'observation et de durée", expanded=True):
                    
                start_date = st.date_input(
                    "Date de début du filtre",
                    value=datetime.now().date(),
                    min_value=datetime.now().date(),
                    key="start_date_input",
                    help="La prédicition couvre les 100 prochaines révolutions officielles de l'ISS (vitesse orbite 28000 km/h).  \nSélectionnez le jour à partir duquel vous souhaitez observer les passages."
                )
                    
                # Avertissement si la date de début est trop loin (la météo simulée devient très peu fiable)
                if (start_date - datetime.now().date()).days > 7:
                    st.warning("⚠️ Attention : La simulation météo devient incertaine au-delà d'une semaine.")


                preferred_time_slot = st.selectbox(
                    "Filtrer par moment optimal",
                    ["Tous", "Aube", "Crépuscule", "Faible Visibilité"], 
                    key="preferred_time_slot_input",
                    help="Les passages les plus visibles sont souvent à l'aube (🌅) ou au crépuscule (🌇)."
                )
                    
                min_duration = st.slider(
                    "Durée minimale de visibilité (secondes)",
                    min_value=10,
                    max_value=600,
                    value=30,
                    step=5,
                    key="min_duration_input",
                    help="Filtrer les passages trop rapides pour une bonne observation (l'ISS se déplace très vite)."
                )
                
                st.markdown("---")
                # Bouton de lancement du traitement
 
                if st.button("Lancer l'analyse prédictive", type="primary", use_container_width=True):
                    # --- LOGIQUE DE GÉO-RÉSOLUTION ---
                    if st.session_state.get('address_input'):
                        # GÉOCODAGE RÉEL
                        resolved_lat, resolved_lon, display_location, geocoding_success = geocode_address(st.session_state['address_input'])
                    else:
                        # MANUEL
                        resolved_lat = lat_manual
                        resolved_lon = lon_manual
                        display_location = f"Lat: {lat_manual:.4f}, Lon: {lon_manual:.4f}"
                        geocoding_success = True 

                    # Stockage des résultats dans session_state et RERUN
                    st.session_state['lat'] = resolved_lat
                    st.session_state['lon'] = resolved_lon
                    st.session_state['display_location'] = display_location 
                    st.session_state['is_processed'] = True
                    st.session_state['geocoding_success'] = geocoding_success

                    # Efface le cache de l'API pour que la nouvelle position soit utilisée
                    fetch_iss_passes.clear()
                    st.rerun()


            # --- ÉTAPE OPTIMISÉE: Traitement centralisé si le bouton a été cliqué ---
            if 'is_processed' in st.session_state and st.session_state['is_processed']:
                # Ceci est exécuté une seule fois par Streamlit run après un bouton/changement
                with st.spinner(f"Traitement des données pour {st.session_state['display_location']}..."):
                    # Met à jour les DataFrames stockés dans st.session_state
                    process_all_data() 
                

        # --- Section Carte ---
        with col_map:
            st.subheader("Visualisation de la zone")

            # DataFrame de l'observateur
            map_df_observer = pd.DataFrame([{
                'lat': st.session_state['lat'],
                'lon': st.session_state['lon'],
                'Type': 'Observateur',
                'Info': st.session_state['display_location']
            }])

            # Figure initiale
            fig_map = px_go.Figure()

            # Trace de l'observateur
            fig_map.add_trace(px_go.Scattermapbox(
                lat=map_df_observer['lat'],
                lon=map_df_observer['lon'],
                mode='markers',
                marker=px_go.scattermapbox.Marker(
                    size=15,
                    symbol='star',
                    color='#FF4B4B',
                    opacity=0.9
                ),
                hovertext=map_df_observer['Info'],
                hoverinfo='text',
                name='Légende'
            ))

            # --- Ajout du point rouge "Vous êtes ici" uniquement si traitement lancé ---
            if st.session_state.get('is_processed'):
                fig_map.add_trace(px_go.Scattermapbox(
                    lat=[st.session_state['lat']],
                    lon=[st.session_state['lon']],
                    mode='markers',
                    marker=px_go.scattermapbox.Marker(
                        size=14,
                        color='#FF0000',
                        opacity=0.95
                    ),
                    hoverinfo='text',
                    hovertext=f"Position utilisateur (approx.)\nLat: {st.session_state['lat']:.4f}, Lon: {st.session_state['lon']:.4f}",
                    name='Votre localisation ici'
                ))

                # Si un passage est disponible, afficher la trajectoire ISS
                df_sorted = st.session_state.get('df_sorted')
                if df_sorted is not None and not df_sorted.empty:
                    best_pass = df_sorted.iloc[0]
                    best_duration = best_pass['Durée (Secondes)']
                    best_time_str = best_pass['Date Heure du Passage (UTC)'].strftime('%d/%m à %H:%M:%S UTC')

                    # Simuler trajectoire
                    df_trajectory = simulate_iss_trajectory(
                        st.session_state['lat'], 
                        st.session_state['lon'],
                        best_duration
                    )

                    fig_map.add_trace(px_go.Scattermapbox(
                        lat=df_trajectory['lat'],
                        lon=df_trajectory['lon'],
                        mode='lines',
                        line=dict(width=3, color='#42A5F5'),
                        hoverinfo='none',
                        name='Trajectoire ISS simulée'
                    ))

                    fig_map.update_layout(title=f"Trajectoire simulée du passage optimal : {best_time_str}")

            # Layout final
            fig_map.update_layout(
                mapbox_style="open-street-map",
                mapbox_zoom=6,
                mapbox_center={"lat": st.session_state['lat'], "lon": st.session_state['lon']},
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                margin={"r":0,"t":50,"l":0,"b":0},
                height=600
            )

            st.plotly_chart(fig_map, use_container_width=True)

            st.caption(f"La carte est centrée sur: **{st.session_state['display_location']}**")
            st.markdown(f"**Coordonnées utilisées:** Lat: `{st.session_state['lat']:.4f}`, Lon: `{st.session_state['lon']:.4f}`")



    # --- FIN ENCADREMENT MODERNE 1 ---
    

    # --- AFFICHAGE DYNAMIQUE DES RÉSULTATS (DASHBOARD) ---

    # --- BOUTONS D'ACTIONS AVANT LES RÉSULTATS ---
    if st.session_state.get('is_processed'):

        with st.container(border=True):
            # Titre centré
            st.markdown("<h4 style='text-align: center;'>💡 Que faire de votre analyse ? </h4>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # Crée 3 colonnes pour les boutons alignés
            col_pdf, col_email_btn, col_agenda = st.columns([1, 1, 1])

            # --- 1️⃣ Export PDF ---
            with col_pdf:
                if st.button("📄 Exporter PDF", use_container_width=True):
                    st.info("Génération du PDF en cours…")
                    generate_pdf()  # ta fonction locale pour PDF

            # --- 2️⃣ Envoyer Email ---
            with col_email_btn:
                if st.button("✉️ Envoyer Email", use_container_width=True):
                    # Affiche le champ email et bouton confirmer seulement après clic
                    email = st.text_input("Adresse email", placeholder="ex: test@domaine.com", key="popup_email_input")
                    if st.button("Confirmer envoi", key="popup_email_btn"):
                        if email:
                            send_email_with_pdf(email)  # ta fonction locale pour envoyer le PDF
                            st.success(f"✅ PDF envoyé à {email}")
                        else:
                            st.warning("Veuillez saisir une adresse email.")

            # --- 3️⃣ Enregistrer dans agenda ---
            with col_agenda:
                if st.button("📅 Booker agenda", use_container_width=True):
                    suggested_slot = get_best_available_slot()  # ta fonction pour trouver le créneau
                    chosen_slot = st.date_input("Choisir un créneau", value=suggested_slot.date(), key="agenda_date")
                    chosen_time = st.time_input("Heure du créneau", value=suggested_slot.time(), key="agenda_time")
                    if st.button("Confirmer le booking", key="agenda_confirm"):
                        add_to_calendar(chosen_slot, chosen_time)  # ta fonction pour ajouter à l'agenda
                        st.success("✅ Créneau enregistré dans votre agenda.")

            st.divider()


        # --- RÉSULTATS ---
            st.header("📊 Résultats de la prédiction et classement")

        # Encadré moderne 2 : statut et résumé
            with st.container(border=True):
                st.subheader("Statut du flux de données et synthèse")

                # Affichage du statut de la connexion API
                api_status = st.session_state.get('api_status_message', '')

                if "Bascule sur données simulées" in api_status:
                    st.info(
                        f"ℹ️ Les prévisions sont basées sur des données simulées.",
                        icon="🛰️"
                    )
                elif api_status:
                    st.success(
                        f"✅ Statut du flux : Connexion API ISS réussie.",
                        icon="📡"
                    )

            summary = st.session_state.get('summary', "Veuillez lancer la prédiction.")
            st.info(f"**Synthèse des passages :** {summary}")

            df_observable_display = st.session_state.get('df_observable_display', pd.DataFrame())
            total_observable_count = st.session_state.get('total_observable_count', 0)

            if total_observable_count == 0:
                st.warning(
                    "Aucun passage n'a été trouvé avec vos critères de filtrage et de visibilité "
                    "(Ciel Dégagé/Peu Nuageux). Essayez de réduire la durée minimale, de changer la date de début, "
                    "ou de sélectionner 'Tous' pour le moment optimal."
                )
            else:
                st.subheader("🏆 Classement des passages observables")

                df_observable_display = df_observable_display.copy()
                df_observable_display.index = np.arange(1, len(df_observable_display) + 1)
                df_observable_display.index.name = 'Rang'

                # Top 10
                df_top_10 = df_observable_display.iloc[0:10]
                st.caption(
                    "🥇 **Top 10 des passages optimaux** (Rang 1 à 10) : "
                    "Meilleure combinaison de visibilité (ISS, Ciel) et de durée."
                )
                st.dataframe(df_top_10, use_container_width=True, column_config=DATAFRAME_COLUMN_CONFIG)

                # Top 11-20
                if total_observable_count > 10:
                    df_next_10 = df_observable_display.iloc[10:20]
                    st.caption("🥈 **Options suivantes** (Rang 11 à 20)")
                    st.dataframe(df_next_10, use_container_width=True, column_config=DATAFRAME_COLUMN_CONFIG)

                # Autres passages si >20
                if total_observable_count > 20:
                    st.caption(
                        f"**{total_observable_count - 20}** passages supplémentaires répondant aux critères "
                        "sont inclus dans la frise chronologique ci-dessous."
                    )

            st.divider()

            # --- GRAPHIQUE CHRONOLOGIQUE UNIQUE AVEC CONTAINER ---
            df_chart_data = st.session_state.get('df_sorted')

            if df_chart_data is not None and not df_chart_data.empty:
                df_chart_data = df_chart_data.copy()
                df_chart_data['Heure du Jour (Décimale)'] = (
                    df_chart_data['Date Heure du Passage (UTC)'].dt.hour
                    + df_chart_data['Date Heure du Passage (UTC)'].dt.minute / 60
                )
                df_chart_data['Date'] = df_chart_data['Date Heure du Passage (UTC)'].dt.date
                df_chart_data['Durée (Min)'] = df_chart_data['Durée (Secondes)'] / 60
                df_chart_data['Label Passage'] = df_chart_data['Durée (Secondes)'].apply(
                    lambda x: f"Durée: {x // 60}m {x % 60}s"
                )
                df_chart_data['Symbole Moment'] = df_chart_data['Moment Sol/Ciel'].apply(get_symbol_display)
                df_chart_data['rank'] = df_chart_data.index + 1

                # Création graphique de base
                fig_time_of_day = px.scatter(
                    df_chart_data,
                    x='Date',
                    y='Heure du Jour (Décimale)',
                    color='Symbole Moment',
                    size='Durée (Min)',
                    hover_name='Label Passage',
                    labels={'Date': 'Jour', 'Heure du Jour (Décimale)': 'Heure (UTC)'},
                    color_discrete_map={
                        "🌅 Aube": "#FFC107",
                        "🌇 Crépuscule": "#FF5722",
                        "☀️ Jour": "#42A5F5",
                        "🌑 Nuit Profonde": "#414040"
                    },
                    title="Répartition des passages par jour et par heure dans la journée"
                )

                # Top10 rouge
                df_top10 = df_chart_data[df_chart_data['rank'] <= 10]
                fig_time_of_day.add_trace(px_go.Scatter(
                    x=df_top10['Date'],
                    y=df_top10['Heure du Jour (Décimale)'],
                    mode='markers',
                    name='Top 10 (Optimal)',
                    marker=dict(color='red', size=df_top10['Durée (Min)']*2.5+10, symbol='circle-open', line=dict(width=3)),
                    customdata=df_top10[['rank', 'Durée (Min)']],
                    hovertemplate='<b>🥇 Rang:</b> %{customdata[0]}<br><b>Durée:</b> %{customdata[1]:.1f} min<extra></extra>'
                ))

                # Top11-20 vert
                df_mid = df_chart_data[(df_chart_data['rank'] > 10) & (df_chart_data['rank'] <= 20)]
                fig_time_of_day.add_trace(px_go.Scatter(
                    x=df_mid['Date'],
                    y=df_mid['Heure du Jour (Décimale)'],
                    mode='markers',
                    name='Top 11-20 (Satisfaisant)',
                    marker=dict(color='green', size=df_mid['Durée (Min)']*2+8, symbol='circle-open', line=dict(width=2)),
                    customdata=df_mid[['rank', 'Durée (Min)']],
                    hovertemplate='<b>🥈 Rang:</b> %{customdata[0]}<br><b>Durée:</b> %{customdata[1]:.1f} min<extra></extra>'
                ))

                # Mise à jour des axes et layout
                fig_time_of_day.update_yaxes(
                    tickvals=list(range(25)),
                    ticktext=[f"{h:02d}:00" for h in range(25)],
                    range=[-1, 25],
                    title="Heure (UTC)"
                )
                fig_time_of_day.update_xaxes(
                    tickangle=45,
                    dtick="D1",
                    tickformat="%d %b"
                )
                fig_time_of_day.update_layout(
                    height=600,
                    legend_title_text='Légende',
                    margin=dict(l=10, r=10, t=50, b=10),
                    yaxis=dict(showgrid=True, gridcolor='lightgray'),
                    xaxis=dict(showgrid=True, gridcolor='lightgray'),
                    showlegend=True
                )

                # Affichage du graphique à l'intérieur du container
                with st.container(border=True):
                    st.subheader("🗓️ Visualisation chronologique des passages observables")
                    st.caption(
                        "**Frise chronologique des passages**  \n La couleur des ronds indique le **moment du jour**. \nLa taille du point est proportionnelle à la **durée du passage**.  \nLes cercles rouges/verts mettent en évidence le **Top10 ou le Top11-20 des passages**."
                    )
                    st.plotly_chart(fig_time_of_day, use_container_width=True)
            else:
                st.warning(
                    "⚠️ Pas assez de données classées pour afficher le graphique. "
                    "Veuillez ajuster vos critères de date, durée ou moment optimal."
                )

# --- FIN DU BLOC ELSE principal ---


if __name__ == '__main__':
    # Initialisation minimale pour éviter les erreurs d'état au démarrage
    if 'lat' not in st.session_state:
        st.session_state['lat'] = DEFAULT_LAT
        st.session_state['lon'] = DEFAULT_LON
        st.session_state['display_location'] = "Paris, France"
    
    main()
