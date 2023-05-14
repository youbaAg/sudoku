from flask import Flask, request, jsonify
import cv2
import numpy as np
from tensorflow.keras.models import load_model
from sudoku_solver import solve

app = Flask(__name__)

@app.route('/solveSudoku', methods=['POST'])
def solve_sudoku():
    # Récupérer l'image de la requête
    fichier = request.files['image']
    image = cv2.imdecode(np.fromstring(fichier.read(), np.uint8), cv2.IMREAD_UNCHANGED)

    # Prétraitement de l'image
    hauteur_img = 450
    largeur_img = 450
    image = cv2.resize(image, (largeur_img, hauteur_img))
    image_gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_floue = cv2.GaussianBlur(image_gris, (5, 5), 1)
    image_seuil = cv2.adaptiveThreshold(image_floue, 255, 1, 1, 11, 2)
    contours, hierarchy = cv2.findContours(image_seuil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Trouver le plus grand contour (grille de sudoku)
    plus_grand_contour = np.array([])
    surface_max = 0
    for contour in contours:
        surface = cv2.contourArea(contour)
        if surface > 50:
            perimetre = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimetre, True)
            if surface > surface_max and len(approx) == 4:
                plus_grand_contour = approx
                surface_max = surface

    # Si la grille de sudoku est trouvée, transformer l'image
    if plus_grand_contour.size != 0:
        plus_grand_contour = plus_grand_contour.reshape((4, 2))
        nouveaux_points = np.zeros((4, 1, 2), dtype=np.int32)
        somme = plus_grand_contour.sum(1)
        nouveaux_points[0] = plus_grand_contour[np.argmin(somme)]
        nouveaux_points[3] = plus_grand_contour[np.argmax(somme)]
        diff = np.diff(plus_grand_contour, axis=1)
        nouveaux_points[1] = plus_grand_contour[np.argmin(diff)]
        nouveaux_points[2] = plus_grand_contour[np.argmax(diff)]
        pts1 = np.float32(nouveaux_points)
        pts2 = np.float32([[0, 0], [largeur_img, 0], [0, hauteur_img], [largeur_img, hauteur_img]])
        matrice = cv2.getPerspectiveTransform(pts1, pts2)
        image_transformee = cv2.warpPerspective(image, matrice, (largeur_img, hauteur_img))
        image_transformee_gris = cv2.cvtColor(image_transformee, cv2.COLOR_BGR2GRAY)
        lignes = np.vsplit(image_transformee_gris, 9)
        cases = []
        for ligne in lignes:
            colonnes = np.hsplit(ligne, 9)
            for case in colonnes:
                cases.append(case)

        # Charger le modèle OCR
        modele = load_model('model-OCR.h5')

        # Effectuer l'OCR sur chaque chiffre
        resultats = []
        for case in cases:
            image_case = np.asarray(case)
            image_case = image_case[4:image_case.shape[0] - 4, 4:image_case.shape[1] - 4]
            image_case = cv2.resize(image_case, (48, 48))
            image_case = image_case / 255
            image_case = image_case.reshape(1, 48, 48, 1)
            predictions = modele.predict(image_case)
            classIndex = np.argmax(predictions, axis=-1)
            probabilityValue = np.max(predictions)
            if probabilityValue > 0.8:
                resultats.append(classIndex[0])
            else:
                resultats.append(0)

        # Résoudre le Sudoku
        resultats = np.asarray(resultats)
        pos_vides = np.where(resultats > 0, 0, 1)
        tableau = np.array_split(resultats, 9)
        try:
            solve(tableau)
        except:
            pass
        liste_aplatie = []
        for sous_liste in tableau:
            liste_aplatie.append(sous_liste.tolist())
        nombres_resolus = [liste_aplatie[i:i + 9] for i in range(0, len(liste_aplatie), 9)]

        # Renvoyer une réponse JSON
        reponse = {
            'solution': nombres_resolus
        }
        return jsonify(reponse)
