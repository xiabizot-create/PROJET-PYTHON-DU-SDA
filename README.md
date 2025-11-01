READ ME PROJET   #   ISS Predictor Pro

DU SDA - PYTHON
Professeur : Alexis BOGROFF
Etudiant : Xia BIZOT


🛰️ Présentation du projet
ISS Predictor Pro est une application interactive développée en Python avec Streamlit permettant de prédire et visualiser les passages optimaux de la Station Spatiale Internationale (ISS) depuis une localisation donnée.
L’objectif est d’aider un observateur amateur ou professionnel à savoir quand et où regarder l’ISS, en prenant en compte :
•	Plus que le tracking de l’ISS, les prévisions de ses révolutions autour de la Terre
•	La géolocalisation navigateur et/ou localisation saisie par l’utilisateur
•	Le moment de la journée (Aube, Crépuscule, Jour, Nuit)
•	La visibilité de l’ISS (Optimale ou Faible)
•	Les conditions météorologiques simulées
•	La durée du passage
L’application propose une analyse claire et facilement lisible des meilleurs résultats issus du scoring multifactoriels des données d’entrée, ainsi qu’un graphique clair qui permet à l’utilisateur de se projeter tant dans le temps que dans l’espace, littéralement.
Elle offre aussi des fonctionnalités pratiques comme la génération de PDF et le partage de l’analyse par email, ainsi que la planification dans un agenda (simulations locales).

________________________________________
📁 Contenu du projet
•	iss_predictor_app.py : script principal Streamlit
•	requirements.txt : fichier listant toutes les dépendances nécessaires pour exécuter l’application localement
•	VISUEL de l’application :

 ________________________________________
Voici le rappel des API utilisées et leurs fonctionnalités :
Fonction / Objectif	API ou source utilisée	Remarques
Tracking de l’ISS	Open-Notify ISS Pass API (http://api.open-notify.org/iss-pass.json)	Permet de récupérer les heures de passage de l’ISS pour des coordonnées GPS données. Si l’API échoue, ton script génère des données simulées.
Moment de la journée (Aube, Crépuscule, Jour, Nuit)	Calcul local dans le script (get_sol_ciel_category)	Déduit le moment de la journée à partir de l’heure UTC du passage. Pas d’API externe.
Visibilité de l’ISS (Optimale ou Faible)	Calcul local dans le script (get_sol_ciel_category)	Déterminée selon le moment de la journée et non via une API externe.
Conditions météorologiques simulées	Simulation locale (get_mock_weather)	Génère aléatoirement un ciel “Dégagé”, “Peu Nuageux”, “Couvert”, ou “Pluvieux”. Pas d’API météo réelle.
Durée du passage de l’ISS	Open-Notify ISS Pass API	L’API renvoie la durée de visibilité pour chaque passage. Les passages simulés respectent la même logique.
En résumé : la seule vraie API externe utilisée est Open-Notify pour le suivi de l’ISS. Le reste (moment de la journée, visibilité et météo) est entièrement calculé ou simulé localement.
Dans le concret, il est préférable d’utiliser un moyen de remplacer la météo simulée par une vraie API météo pour rendre ton application plus réaliste.


⚙️ Fonctionnement général
1.	Configuration initiale
o	Saisie d’une adresse ou utilisation de la géolocalisation automatique du navigateur.
o	Calcul des coordonnées GPS via geopy/Nominatim si une localisation est saisie.
o	Valeurs par défaut : Paris, France.
2.	Filtrage et préférences
o	Date de début du calcul des passages.
o	Moment optimal pour observer (Aube, Crépuscule, Tous, Faible Visibilité).
o	Durée minimale des passages (secondes).
3.	Récupération des données ISS
o	Tentative via l’API Open-Notify.
o	En cas d’échec, génération de données simulées localement.
4.	Traitement des données
o	Calcul de la visibilité ISS (optimale ou faible).
o	Simulation météo pour chaque passage (ciel dégagé, peu nuageux, couvert, pluvieux).
o	Attribution d’un score composite pour classer les passages selon visibilité et météo.
o	Préparation des DataFrames pour l’affichage et les graphiques.
5.	Affichage et visualisation
o	Carte interactive avec position de l’observateur Vs trajectoire ISS simulée.
o	Tableau des passages observables, triés par score.
o	Graphique chronologique des passages par jour et heure pour les 100 prochaines révolutions monitorées au planning de l’ISS.
6.	Actions supplémentaires
o	Export PDF simulé
o	Envoi email simulé
o	Ajout d’un créneau dans l’agenda

________________________________________
🧰 Technologies et bibliothèques utilisées
•	Python 3.11+
•	Streamlit : interface web interactive
•	streamlit-js-eval : récupération de la géolocalisation via navigateur
•	requests : appels HTTP vers l’API ISS
•	pandas & numpy : manipulation et calculs de données
•	geopy : géocodage d’adresses
•	plotly : visualisation graphique et carte interactive

________________________________________
🚀 Exécution en local
1.	Installer Python 3.11+
2.	Installer les dépendances :
pip install -r requirements.txt
3.	Lancer l’application :
streamlit run iss_predictor_app.py
L’application s’ouvrira dans votre navigateur par défaut.

Détail complet :
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

________________________________________
📝 Remarques pédagogiques
•	Intégration de données externes et locales pour produire des résultats fiables même en cas d’échec de l’API.
•	Utilisation de DataFrames pour traiter efficacement les données et appliquer des filtres complexes.
•	Mise en œuvre de Streamlit pour un affichage interactif avec cartes, graphiques et tableaux.
•	Code organisé pour séparer les fonctions utilitaires, la logique métier et l’interface utilisateur.

________________________________________
💡 Conclusion
ISS Predictor Pro est un outil pédagogique et pratique pour explorer les passages de l’ISS, comprendre la visibilité selon les conditions temporelles et météorologiques, et découvrir comment traiter et visualiser des données scientifiques en Python.


📝 Remarques personnelles
J’imagine ce projet inscrit dans le cadre d’une campagne de communication de l’ESA et la NASA, couplée à une communication gouvernementale autour de la prochaine mission de l’astronaute française Sophie Adenot, qui saura très certainement créer autant d’engouement que Thomas Pesquet. Le message véhiculé serait de susciter l’intérêt pour les métiers scientifiques. En théorie, ce projet ne rapporterait pas d’argent car l’utilité est très restreinte. Elle peut permettre par exemple de planifier les communications avec la station, l’observation de ses passages, par exemple pour des programmes de recherche ou scolaires.
En dehors de cette application très limitée, ce système pourrait être élargi à des applications privées, notamment dans le cadre d’activités de sociétés comme Thales Alenia ou SpaceX. L’intérêt est transférable au monitoring des satellites et autres objets, surtout au vu de l’état actuel de l’espace terrien. Le développement des nouvelles technologies de communication, et donc intrinsèquement celui de la pollution spatiale est en outre un autre sujet qui sera porteur. Le nombre de débris spatiaux dont la taille est supérieure à 1 mm est estimé aujourd’hui à environ 128 millions.
