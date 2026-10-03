"""Start Jupyter with this config to avoid saving confidential notebook outputs."""


def clear_saved_outputs(model, **kwargs):
    if model.get("type") != "notebook":
        return
    notebook = model["content"]
    notebook.get("metadata", {}).pop("widgets", None)
    for cell in notebook.get("cells", []):
        cell.pop("attachments", None)
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None


c = get_config()
c.ContentsManager.pre_save_hook = clear_saved_outputs
