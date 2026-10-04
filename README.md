# L2C — Du plan aux dessins d’atelier

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
6. Générer un rapport PDF organisé par feuille de plan, avec les écarts et les extraits justificatifs.

Les extractions et associations incertaines sont signalées pour validation. Une information illisible ou absente ne doit pas être présentée comme une non-conformité confirmée.

## Données à extraire

- Document, feuille et zone source.
- Type d’élément structural et repère.
- Diamètre et quantité des barres.
- Espacement et dimensions.
- Forme, ancrage et recouvrement lorsque disponibles.
- Niveau de confiance de l’extraction et de l’association.

Exemple illustratif de structure JSON :

```json
{
  "document": "plan_construction.pdf",
  "feuille": "S-201",
  "element": { "type": "poutre", "repere": "P12" },
  "armature": {
    "diametre_mm": 20,
    "quantite": null,
    "espacement_mm": 150
  },
  "source": { "page": 3, "zone": [120, 240, 480, 360] },
  "confiance": 0.92
}
```

Les coordonnées de cet exemple sont illustratives ; leur unité et leur origine devront être définies dans le schéma final. Les unités et désignations d’armature seront adaptées aux documents fournis.

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

Ce README décrit le concept et le périmètre envisagé. Le prototype n’est pas encore implémenté. Le rapport sert d’aide à la vérification et les constats doivent être validés par les professionnels responsables.

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

Current implementation: dataset inspection only. Extraction, matching and discrepancy reporting are not implemented yet.

## Local ML smoke benchmark

The optional ML environment uses `requirements-ml.txt` plus CPU PyTorch and torchvision from the official PyTorch wheel index. It is separate from the basic inventory environment.

`python -m l2c.prepare_samples --pdf <local-pdf> --page 37 --output-dir <local-private-folder>` prepares three image crops around native bar-designation candidates. `python -m l2c.ml_benchmark --backend florence --model-dir <downloaded-model-folder> --samples <local-private-folder>/samples.json --output <local-private-folder>/florence-results.json` runs Florence-2-base. Use `--backend paddle` for PP-OCRv5 mobile detection and recognition.

Download model weights first, then run inference locally. Set HF_HOME and PADDLE_PDX_CACHE_HOME to local folders outside this repository. Raw samples and model outputs contain confidential content and must stay outside cloud-synced folders and Git.

This three-crop test measures runtime and agreement with native PDF bar designations. It does not measure manually verified accuracy, element association, spacing/length extraction or discrepancy detection. Crop selection based on native text also biases the test toward text-bearing regions; broader validation is required.

## Jupyter notebook

`notebooks/demo_l2c.ipynb` demonstrates the implemented inventory, crop preparation and optional local ML benchmark. It explicitly marks extraction to Annex A, matching and PDF reporting as pending.

From the repository root:

```powershell
python -m pip install -r requirements-notebook.txt
python -m jupyterlab --config=jupyter_server_config.py
```

Open the notebook and select the matching Python kernel. Set its local DATA_DIR and OUTPUT_DIR. Optional inference requires CPU PyTorch and requirements-ml.txt in that same kernel environment, plus local model weights. ML execution is disabled by default.

The supplied Jupyter server configuration clears outputs, execution counts, widget state and attachments on save. Always launch with that configuration. Outputs can contain confidential document data; other notebook editors may not apply this hook. Never put confidential text or images into notebook source cells. Keep data and results outside OneDrive and Git.

## Annotation-to-element association

`l2c.associate.associate_annotations(annotations, elements)` associates reinforcement annotations within a source document. It does not match plans to shop drawings or detect discrepancies.

Annotations supply Annex A source fields, a unique annotation id, parsed armature, x/y, and optionally text, bbox, element_ref, leader_endpoint, schedule_ref and direction. Elements supply the same source/page fields, element and type_element, plus optional bbox and schedule_ref. Coordinates must be PDF points relative to the displayed page's upper-left corner. Source file, sheet and page must agree before an association is considered.

Supported evidence: exact element identifiers, leader endpoints inside element regions, annotation containment and shared marker-to-schedule references. Conflicting candidates become ambiguous; absent evidence becomes unresolved. Shared schedules can intentionally produce records for several elements. A schedule_ref must be unique to its table/type context, not merely a letter such as C. This module consumes detected or manually verified context; automatic marker, grid and leader detection is not implemented. Heuristics have not been calibrated into probability scores.

Run on a local input JSON containing annotations and elements:

```powershell
python -m l2c.associate --input "<local-input.json>" --output-dir "<local-output-folder>"
```

Outputs are annex-a.json and associations.json. The latter preserves unresolved cases, evidence, direction and provenance. The downstream consumer must avoid counting shared schedule references as independent quantities. Unknown armature attributes remain null.

Paddle benchmark outputs now retain OCR polygons and recognition scores locally. Rerun prepare_samples to include crop transforms; new Paddle results map those polygons into PDF points. This is not full-page extraction or automatic structural-element detection.

Validation: five synthetic tests cover page isolation, overlapping regions, conflicting references, shared schedules and external leaders. The CLP L-13 sample additionally verifies four schedule annotations with manually confirmed marker relationships. These checks do not establish dataset-wide association accuracy.
