# Démonstration L2C — 10 minutes

## 0–1 min : problème et architecture

Comparer les armatures entre plans et dessins d'atelier, avec une preuve fichier/page/coordonnées. Python orchestre l'extraction native PyMuPDF, l'OCR PaddleOCR local, l'association par repères/géométrie/tableaux, la validation Pydantic et le rapport ReportLab.

## 1–3 min : choix du modèle et extraction

Sur 12 extraits issus des quatre projets, Paddle a pris en moyenne 2,078 s par extrait contre 13,572 s pour Florence. Accord avec le texte PDF natif : 24/24 tokens de diamètre et 14/14 couples quantité/diamètre pour Paddle. Ce petit benchmark mesure l'accord sur des extraits sélectionnés, pas la précision des écarts sur tout le projet. Aucun modèle n'a été entraîné ou affiné par l'équipe.

Montrer `notebooks/demo_l2c.ipynb`, une annotation et son centre X/Y en points PDF depuis le coin supérieur gauche. Les données inconnues restent null ; les preuves et incertitudes sont enregistrées séparément du JSON Annexe A.

## 3–6 min : exécution en direct

Depuis le répertoire du code, avec les dépendances déjà installées :

```powershell
python -m l2c.pipeline --project-dir "C:\donnees\PROJET_JURY" --output-dir "C:\resultats\PROJET_JURY" --ocr hybrid --models-dir "C:\modeles"
```

Le dossier de modèles doit contenir `PP-OCRv5_mobile_det` et `PP-OCRv5_mobile_rec`. Les poids Paddle préchargés sont inclus dans le paquet privé de remise sous `models/`. Toutes les inférences restent locales. Le traitement complet sur CPU peut dépasser la durée de la présentation. `--max-pages` et `--max-ocr-pages` permettent une démonstration limitée ; annoncer explicitement cette limitation. Ne pas réutiliser le contexte manuel CLP sur le projet du jury.

Pour vérifier rapidement l'installation, sans données confidentielles ni poids :

```powershell
python -m l2c.demo_project --project-dir "C:\resultats\demo-input" --output-dir "C:\resultats\demo-output"
```

Cette démonstration synthétique couvre cinq types d'éléments, quatre écarts (quantité, diamètre, espacement, longueur), une conformité et une annotation non associée. Elle complète la démonstration du projet du jury.

## 6–8 min : preuve et rapport

Ouvrir `annex-a.json`, `coverage.json`, `reconciliation.json` puis `report.pdf`. Le rapport regroupe les résultats par feuille et distingue les écarts confirmés des cas à vérifier.

Exemple CLP vérifié avec un contexte fourni par un réviseur : S-100, L-13, page 4 du plan, type C : 9-25M ; page 1 de `CLP_SEMELLES FND.pdf`, type B : 11-25M. Deux directions présentent le même écart de quantité. Présenter l'association L-13 comme assistée par le réviseur.

## 8–10 min : validation et limites

41 tests ont passé. Le notebook a été exécuté avec et sans ML. Les sorties des quatre projets totalisent 611 pages analysées et 2 192 enregistrements Annexe A ; ce nombre ne mesure pas la précision. Les 244 pages des rapports ont été rendues localement et contrôlées pour débordements de texte.

La couverture reste partielle : 334 pages candidates à l'OCR ont été omises par le budget de traitement des trois autres projets ; beaucoup d'annotations restent sans association. La notation `16(8)` et certains repères de barre ne sont pas interprétés. Les éléments manquants/ajoutés sont conservés comme cas à vérifier lorsque la couverture ne permet pas de conclure. La généralisation au projet inédit du jury n'a pas encore été mesurée.

## Installation et remise

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-notebook.txt
# Pour l'OCR : installer PyTorch CPU, puis requirements-ml.txt, selon README.md.
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Le paquet privé contient le code, le notebook sans sorties confidentielles, les dépendances, les modèles préentraînés Paddle, les JSON/PDF des quatre projets et les audits. Conserver ce paquet localement et le remettre au jury ; les résultats des documents fournis ne doivent pas être publiés dans un dépôt public. Les données et sorties doivent être supprimées après l'événement selon les consignes.
