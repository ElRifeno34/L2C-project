# L2C — Du plan aux dessins d’atelier

> État de remise : prototype local exécutable, 41 tests validés, notebook exécuté avec et sans ML, JSON/PDF des quatre projets générés. La couverture reste partielle. Voir [DEMO.md](DEMO.md) pour les commandes, la démonstration et les limites mesurées.


## Idée du projet

Un vérificateur d’armatures qui compare les plans de construction aux dessins d’atelier et relie chaque écart à sa preuve dans les documents.

Le projet répond au challenge L2C : extraire les caractéristiques des armatures en JSON, associer les éléments entre les documents et produire un rapport PDF des écarts par feuille de plan. **Python est obligatoire.** Les données et les critères détaillés seront fournis au lancement.

## Problème et utilisateurs

La vérification manuelle exige de retrouver les éléments correspondants dans plusieurs feuilles et de comparer leurs caractéristiques. Un écart de diamètre, de quantité ou d’espacement peut être difficile à repérer.

La solution vise les ingénieurs, les techniciens et les équipes chargées de vérifier les dessins d’atelier d’armature.

## Fonctionnement proposé

1. Importer les plans de construction et les dessins d’atelier.
2. Extraire les textes, tableaux et annotations ; utiliser l’OCR lorsque nécessaire.
3. Structurer les caractéristiques des armatures en JSON, avec leur feuille et leur position dans le document.
4. Associer les éléments à partir des repères, axes, types et dimensions.
5. Comparer les caractéristiques selon les règles du challenge.
6. Générer un rapport PDF organisé par feuille de plan, avec les écarts et les références fichier/page/coordonnées.

Les extractions et associations incertaines sont signalées pour validation. Une information illisible ou absente ne doit pas être présentée comme une non-conformité confirmée.

## Données à extraire

- Document, feuille et zone source.
- Type d’élément structural et repère.
- Diamètre et quantité des barres.
- Espacement et dimensions.
- Forme, ancrage et recouvrement lorsque disponibles.
- Niveau de confiance de l’extraction et de l’association.

Exemple conforme à la structure de l’annexe A (valeurs synthétiques) :

```json
{
  "id": "S-500_C-12_plan",
  "source": "plan",
  "fichier": "Projet1_S-500.pdf",
  "feuillet": "S-500",
  "page": 1,
  "x": 412.5,
  "y": 318.0,
  "type_element": "colonne",
  "element": "C-12",
  "armature": [{"repere": "C12-1", "diametre": "25M", "quantite": 8,
                "espacement_mm": null, "longueur_mm": 3600}]
}
```

X/Y sont en points PDF (1/72 po), depuis le coin supérieur gauche de la page, au centre de l’annotation. Les attributs inconnus restent `null`. Notre convention locale pour les dessins d’atelier est `source="atelier"`. Les preuves, directions et incertitudes sont conservées séparément du JSON Annexe A.

## Première version visée

Commencer par les poutres et vérifier le diamètre, la quantité, l’espacement et les dimensions. Démontrer toute la chaîne sur un périmètre limité : document source → JSON → association → comparaison → PDF.

Exemple de constat : **Poutre P12 — plan : Ø20 à 150 mm ; dessin d’atelier : Ø15 à 200 mm**, accompagné des extraits des deux documents.

## Approche technique envisagée

- Python pour le pipeline d’analyse et de génération.
- Extraction PDF et OCR selon la nature des fichiers.
- IA pour interpréter les annotations et proposer des associations.
- Règles explicites pour comparer les valeurs extraites.
- Génération PDF pour présenter les résultats et leurs preuves.

Les bibliothèques seront choisies après inspection des données du challenge.

## Livrables attendus

- Caractéristiques extraites en JSON.
- Associations entre éléments des plans et dessins d’atelier.
- Rapport PDF des écarts par feuille de plan.
- Liste des cas nécessitant une validation humaine.

## Évaluation et état du projet

L2C évaluera le projet selon le document fourni ; aucun score automatique n’est prévu sur HxBuddy. Les règles de comparaison et la validation seront alignées sur ce document.

État réel : inventaire, OCR sur crops, association à partir de contexte fourni, validation Annexe A, matching JSON et rapport PDF sont implémentés. La CLI PDF de projet → extraction → association → JSON → PDF est disponible; la couverture de l’association automatique reste partielle. Le rapport sert d’aide à la vérification et les constats doivent être validés par les professionnels responsables.

## Step 1: local dataset inspection

Use Python 3.12 and install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the inventory from the repository root. Choose an output folder outside this repository and outside cloud-synced folders:

```powershell
python -m l2c.inspect --data-dir "C:\Users\Admin\Downloads\l2c-participants" --output "C:\Users\Admin\Documents\Codex\l2c-local\inventory.json"
```

The inventory records PDF page counts, file sizes, read errors and spreadsheet dimensions. Add `--sample-text` to measure first-page text availability locally. This is only a first-page heuristic, not a complete OCR assessment. Drawing text and spreadsheet cell values are never included in the inventory.

Challenge documents must remain local: no cloud uploads or external AI APIs. Keep input PDFs, extracted JSON, crops, reports and model-derived confidential content outside this OneDrive repository. Git ignore rules are an additional safeguard, not a replacement for storing results elsewhere. Remove challenge data at the end of the event as required by the instructions.

Implemented: inspection, local crop OCR, context-based association, Annex A validation, JSON matching and PDF generation. Project-level PDF integration is available through l2c.pipeline. General element/context detection remains incomplete; unresolved annotations are retained.

## Local ML smoke benchmark

The optional ML environment uses `requirements-ml.txt` plus CPU PyTorch and torchvision from the official PyTorch wheel index. It is separate from the basic inventory environment.

`python -m l2c.prepare_samples --pdf <local-pdf> --page 37 --output-dir <local-private-folder>` prepares three image crops around native bar-designation candidates. `python -m l2c.ml_benchmark --backend florence --model-dir <downloaded-model-folder> --samples <local-private-folder>/samples.json --output <local-private-folder>/florence-results.json` runs Florence-2-base. Use `--backend paddle` for PP-OCRv5 mobile detection and recognition.

Download model weights first, then run inference locally. Set HF_HOME and PADDLE_PDX_CACHE_HOME to local folders outside this repository. Raw samples and model outputs contain confidential content and must stay outside cloud-synced folders and Git.

This three-crop test measures runtime and agreement with native PDF bar designations. It does not measure manually verified accuracy, element association, spacing/length extraction or discrepancy detection. Crop selection based on native text also biases the test toward text-bearing regions; broader validation is required.

## Jupyter notebook

`notebooks/demo_l2c.ipynb` demonstrates the implemented inventory, crop preparation and optional local ML benchmark. It also runs the project PDF-to-Annex-A-to-report pipeline and validates the resulting records. Coverage and unresolved cases are explicitly displayed.

From the repository root:

```powershell
python -m pip install -r requirements-notebook.txt
python -m jupyterlab --config=jupyter_server_config.py
```

Open the notebook and select the matching Python kernel. Set its local DATA_DIR and OUTPUT_DIR. Optional inference requires CPU PyTorch and requirements-ml.txt in the kernel environment (or set L2C_ML_PYTHON to a separate interpreter). Paddle is the default benchmark backend; set L2C_ML_BACKENDS=paddle,florence and L2C_FLORENCE_MODEL_DIR for an optional Florence comparison. ML execution is disabled by default.

The supplied Jupyter server configuration clears outputs, execution counts, widget state and attachments on save. Always launch with that configuration. Outputs can contain confidential document data; other notebook editors may not apply this hook. Never put confidential text or images into notebook source cells. Keep data and results outside OneDrive and Git.

## Annotation-to-element association

`l2c.associate.associate_annotations(annotations, elements)` associates reinforcement annotations within a source document. It does not match plans to shop drawings or detect discrepancies.

Annotations supply Annex A source fields, a unique annotation id, parsed armature, x/y, and optionally text, bbox, element_ref, leader_endpoint, schedule_ref and direction. Elements supply the same source/page fields, element and type_element, plus optional bbox and schedule_ref. Coordinates must be PDF points relative to the displayed page's upper-left corner. Source file, sheet and page must agree before an association is considered.

Supported evidence: exact element identifiers, leader endpoints inside element regions, annotation containment and shared marker-to-schedule references. Conflicting candidates become ambiguous; absent evidence becomes unresolved. Shared schedules can intentionally produce records for several elements. A schedule_ref must be unique to its table/type context, not merely a letter such as C. The project pipeline detects some vector footing markers and paired grid axes; generic leader detection remains unimplemented. Heuristics have not been calibrated into probability scores.

Run on a local input JSON containing annotations and elements:

```powershell
python -m l2c.associate --input "<local-input.json>" --output-dir "<local-output-folder>"
```

Outputs are annex-a.json and associations.json. The latter preserves unresolved cases, evidence, direction and provenance. The downstream consumer must avoid counting shared schedule references as independent quantities. Unknown armature attributes remain null.

Paddle benchmark outputs now retain OCR polygons and recognition scores locally. Rerun prepare_samples to include crop transforms; new Paddle results map those polygons into PDF points. This is not full-page extraction or automatic structural-element detection.

Validation: five synthetic tests cover page isolation, overlapping regions, conflicting references, shared schedules and external leaders. The CLP L-13 sample additionally verifies four schedule annotations with manually confirmed marker relationships. These checks do not establish dataset-wide association accuracy.

Tests sans dépendance pytest : `python -m unittest discover -s tests -v`. Cette commande découvre aussi les tests de fixtures du matching.


## CLI de comparaison disponible

```powershell
python src/reconcile_cli.py "<JSON Annexe A local>" --out "<dossier local hors Git et OneDrive>/rapport.pdf"
```

La CLI valide les enregistrements avec Pydantic avant le matching et bloque les rapports dans Git/OneDrive. Elle prend actuellement un JSON, **pas les PDF d’un projet** : pour l’entrée PDF complète, utiliser `python -m l2c.pipeline` ci-dessous. Exécuter chaque projet séparément.

Les fixtures historiques `tests/sample_cases.json` sont synthétiques : certaines sources/coordonnées et listes vides ne respectent pas l’Annexe A. Pour tester uniquement le moteur de matching/PDF avec ces fixtures :

```powershell
python src/reconcile_cli.py tests/sample_cases.json --mock-input --out "<dossier local hors Git et OneDrive>/mock-report.pdf"
```

Ne pas utiliser `--mock-input` pour les données réelles. Les compteurs `manquant` et `ajoute` sont inclus dans `non_conforme`; ils ne doivent pas être additionnés à nouveau. `a_verifier` est un compteur supplémentaire de cas incertains, séparé des quatre catégories demandées, pas une conformité ni une non-conformité confirmée.


### Matching safeguards

Reinforcement, including repeated bar marks, is compared with quantities attached to diameter, spacing and length; reordered or split identical groups remain equivalent. Missing extraction, entirely unknown bar values and uncertain quantity aggregation produce `À VÉRIFIER`, counted under `a_verifier` in reconciliation output and separately in the PDF. Annex A input fields are unchanged.

Repeated element names in multiple file/sheet/page locations are not merged automatically: each plan location is flagged for explicit instance association. This conservative fallback does not infer floors or match by sheet number, since plan and workshop sheets can differ. Multiple annotations for a name within one document page still merge; distinguishing separate instances on that page requires upstream association. Reviewed instance identities and longitudinal/transverse directions can be supplied through separate context metadata. They are used by the matcher without changing Annex A fields.

Regression checks: `python -m unittest discover -s tests -v` and `python tests/test_match_cases.py`.

## Conformité et limites pour la remise

- Le cœur Python, le JSON Annexe A validé et la génération PDF sont présents.
- Le notebook explore les données, le benchmark OCR et exécute la chaîne PDF → JSON → rapport sur un projet. Les associations non résolues restent visibles.
- Le CLP L-13 est un échantillon avec association confirmée manuellement; il ne prouve pas la généralisation.
- Un JSON/PDF peut être produit pour chacun des quatre projets; une sortie produite ne signifie pas une extraction exhaustive. Les compteurs de couverture doivent accompagner la remise.
- L’extraction automatique, les cinq types d’éléments et le projet inconnu du jury doivent encore être validés. Les nombres du benchmark OCR ne constituent pas rappel/précision des non-conformités.
- Les modèles sont préentraînés; aucun modèle n’a été entraîné/affiné dans ce dépôt. Les poids et scripts d’entraînement ne sont donc pas un livrable applicable à ce stade. Précharger les poids publics avant une démonstration sans réseau.
- Une démonstration de 10 minutes doit inclure l’exécution sur le projet d’évaluation. La vidéo OCR seule ne satisfait pas cette exigence.
- Les critères officiels sont : détection 30, extraction/JSON 20, rapport 15, qualité technique 15, généralisation 10, présentation 10. Aucun score jury n’est revendiqué.

## Exécution complète sur les PDF d’un projet

Depuis la racine du dépôt, environnement Python 3.12 :

```powershell
python -m pip install -r requirements.txt
python -m l2c.pipeline --project-dir "C:\Users\Admin\Downloads\l2c-participants\CLP" --output-dir "C:\Users\Admin\Documents\L2C-results\CLP" --ocr off
```

Mode natif : sans poids ML; utile pour les PDF vectoriels et pour tester l’installation. Mode `auto` : OCR des pages pauvres en texte, y compris les grandes images avec un cartouche vectoriel. Mode `hybrid` : mode auto et vérification de crops natifs par Paddle. La comparaison ML ne remplace pas automatiquement un texte natif en cas de désaccord; le cas est signalé pour revue. Les doublons des tuiles OCR sont supprimés selon le texte et le recouvrement spatial.

Installer l’environnement ML avant la démonstration (poids publics téléchargés sans documents) :

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ml.txt
python -m l2c.models --models-dir "C:\Users\Admin\Documents\L2C-models" --download
python -m l2c.models --models-dir "C:\Users\Admin\Documents\L2C-models"
python -m l2c.pipeline --project-dir "C:\Users\Admin\Downloads\l2c-participants\CLP" --output-dir "C:\Users\Admin\Documents\L2C-results\CLP" --ocr hybrid --models-dir "C:\Users\Admin\Documents\L2C-models"
```

L’inférence utilise les deux répertoires locaux `PP-OCRv5_mobile_det` et `PP-OCRv5_mobile_rec`. Aucun document n’est envoyé à un service externe. Le benchmark local élargi sur 12 crops de quatre projets a obtenu : Paddle 14/14 couples quantité–diamètre, 2,078 s/crop; Florence 4/14, 13,572 s/crop. Référence : texte PDF natif, crops sélectionnés à partir du natif; ni vérité terrain manuelle ni score de détection des non-conformités. Paddle est retenu pour cette machine. [Documentation officielle Paddle](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html), [Florence-2-base](https://huggingface.co/microsoft/Florence-2-base).

Sorties dans le dossier local choisi :

- `annex-a.json` : enregistrements associés et validés, schéma Annexe A uniquement.
- `annotations.json` : tous les callouts reconnus, même non associés.
- `associations.json` : preuves, directions, incertitudes et références.
- `coverage.json` : pages traitées et compteurs d’association.
- `reconciliation.json` : résultats par feuille.
- `run-summary.json` : durée, erreurs et limites.
- `report.pdf` : comptes par feuille, écarts, couverture et références non résolues.

Un code de sortie 2 signale les erreurs ou fichiers non classifiés; conserver run-summary.json pour diagnostic. Les sorties partielles ne doivent pas être présentées comme une vérification exhaustive. `--max-pages` sert uniquement aux essais rapides. Exécuter chaque projet séparément. Le classement des sources reconnaît `L2C_PLAN_STR*.pdf` et les PDF sous `DA`.

`--max-ocr-pages 2` permet un essai ML court sur deux pages candidates tout en traitant le texte natif de toutes les pages. C’est un essai partiel : `ocr_processed_pages`, `ocr_skipped_pages`, `limited_run` et le PDF indiquent sa couverture. Sans cette option, le mode auto/hybrid traite toutes les pages candidates. Le mode natif signale aussi les pages où l’OCR a été omis. Le temps sur les grandes feuilles dépend du nombre de tuiles et doit être mesuré avant la démo.

### Association et corrections locales

Associations automatiques : identifiant explicite dans le même segment texte, cadre de détail contenant un identifiant unique, et cas de semelles où marqueur fermé, axes de grille appariés et ligne TYPE du tableau sont tous reconnus. Les cas ambigus restent non résolus. Ces règles ne constituent pas un détecteur entraîné de tous les éléments structuraux.

Les contours CAD sont reconstruits en cycles fermés, même si les tracés PDF sont séparés ou regroupés. Les lignes ouvertes ou avec embranchements sont exclues. L’ordre des axes lettre/nombre peut être inversé. Une région vérifiée remplace le contexte automatique pour les annotations qu’elle contient; elle ne constitue pas une validation de tous les éléments utilisant le même tableau. Les longueurs explicites ne sont pas propagées à la prochaine annotation. Pydantic refuse les valeurs non finies ainsi que les identifiants et références vides.

Un fichier `--context` local peut préciser des régions vérifiées par l’ingénieur. Exemple synthétique :

```json
{"regions": [{"source": "plan", "fichier": "L2C_PLAN_STR_demo.pdf", "page": 1,
              "bbox": [100, 100, 180, 125], "element": "C-12", "type_element": "colonne",
              "direction": "longitudinale", "instance_id": "NIVEAU-1:C-12"}]}
```

Les boîtes sont en points PDF, origine supérieure gauche; le fichier est relatif au dossier projet. Utiliser un `instance_id` commun aux deux sources seulement quand l’identité physique a été vérifiée. Le contexte est conservé hors Git/OneDrive. Les associations manuelles sont déclarées dans les preuves et ne doivent pas être présentées comme une prédiction automatique. Les directions sont utilisées pendant le matching sans ajouter de champs au JSON Annexe A.

### Notebook et démonstration de 10 minutes

Installer `requirements-notebook.txt`, lancer Jupyter avec la configuration fournie, puis Restart Kernel and Run All. Le notebook utilise CLP par défaut. Pour l’OCR, configurer `L2C_ML_PYTHON` si l’interpréteur est séparé et `L2C_OCR_MODELS_DIR`; pour des régions vérifiées, `L2C_CONTEXT_FILE`. `L2C_MAX_OCR_PAGES` est un budget facultatif déclaré pour un essai partiel. Le benchmark Paddle utilise les poids locaux indiqués. Les résultats sont externes au dépôt.

Déroulé : 1 minute problème/architecture; 2 minutes extraction et OCR local; 3 minutes exécution du pipeline; 2 minutes rapport, écarts et preuves; 2 minutes couverture, limites et questions. Le projet du jury doit être exécuté en direct. Les cinq types sont couverts par des tests synthétiques; leur généralisation sur les vrais plans n’est pas établie. Aucun rappel/précision jury n’est revendiqué.

Démo reproductible sans données confidentielles :

```powershell
python -m l2c.demo_project --project-dir "C:\Users\Admin\Documents\L2C-demo\input" --output-dir "C:\Users\Admin\Documents\L2C-demo\output"
```

Elle produit des PDF synthétiques pour semelle, poutre, mur, colonne et dalle, puis exécute le vrai pipeline. Résultat attendu : quatre écarts (quantité, diamètre, espacement, longueur), une conformité et une annotation non résolue. Les feuilles des ateliers diffèrent de celles des plans. Ce test ne remplace pas l’exécution sur le projet réel d’évaluation.

### Dépendances et remise

PyMuPDF est utilisé via sa distribution open source AGPL; aucune licence commerciale n’est nécessaire pour exécuter ce prototype. Les autres dépendances et leurs licences doivent être conservées lors de la redistribution. Les modèles préentraînés n’ont pas été affinés : aucun script/poids d’entraînement d’équipe à remettre. Précharger les poids et vérifier l’installation du jury.

Avant remise : exécuter les tests, valider les JSON, conserver les rapports/compteurs des quatre projets, réviser les cas non résolus prioritaires, puis commit/push du code uniquement. Ne jamais inclure les PDF, crops ou sorties confidentielles dans le dépôt public. Supprimer les données après l’événement selon les consignes.
