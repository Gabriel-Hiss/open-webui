from typing import Optional
import io
import base64

from open_webui.models.models import (
    ModelForm,
    ModelModel,
    ModelResponse,
    ModelUserResponse,
    Models,
)

from pydantic import BaseModel
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.responses import FileResponse, StreamingResponse


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access, has_permission
from open_webui.config import BYPASS_ADMIN_ACCESS_CONTROL, STATIC_DIR
from open_webui.utils.models import get_all_models as utils_get_all_models, get_all_base_models
import aiohttp, base64, os, re
from pathlib import Path
from aiocache import caches

router = APIRouter()


###########################
# GetModels
###########################


@router.get("/", response_model=list[ModelUserResponse])
async def get_models(id: Optional[str] = None, user=Depends(get_verified_user)):
    if user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL:
        return Models.get_models()
    else:
        return Models.get_models_by_user_id(user.id)


###########################
# GetBaseModels
###########################


@router.get("/base", response_model=list[ModelResponse])
async def get_base_models(user=Depends(get_admin_user)):
    return Models.get_base_models()


############################
# CreateNewModel
############################


@router.post("/create", response_model=Optional[ModelModel])
async def create_new_model(
    request: Request,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    if user.role != "admin" and not has_permission(
        user.id, "workspace.models", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.get_model_by_id(form_data.id)
    if model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.MODEL_ID_TAKEN,
        )

    else:
        model = Models.insert_new_model(form_data, user.id)
        if model:
            return model
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.DEFAULT(),
            )


############################
# ExportModels
############################


@router.get("/export", response_model=list[ModelModel])
async def export_models(user=Depends(get_admin_user)):
    return Models.get_models()


############################
# SyncModels
############################


class SyncModelsForm(BaseModel):
    models: list[ModelModel] = []


@router.post("/sync", response_model=list[ModelModel])
async def sync_models(
    request: Request, form_data: SyncModelsForm, user=Depends(get_admin_user)
):
    return Models.sync_models(user.id, form_data.models)


###########################
# GetModelById
###########################


# Note: We're not using the typical url path param here, but instead using a query parameter to allow '/' in the id
@router.get("/model", response_model=Optional[ModelResponse])
async def get_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if model:
        if (
            (user.role == "admin" and BYPASS_ADMIN_ACCESS_CONTROL)
            or model.user_id == user.id
            or has_access(user.id, "read", model.access_control)
        ):
            return model
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


###########################
# GetModelById
###########################


@router.get("/model/profile/image")
async def get_model_profile_image(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if model:
        if model.meta.profile_image_url:
            if model.meta.profile_image_url.startswith("http"):
                return Response(
                    status_code=status.HTTP_302_FOUND,
                    headers={"Location": model.meta.profile_image_url},
                )
            elif model.meta.profile_image_url.startswith("data:image"):
                try:
                    header, base64_data = model.meta.profile_image_url.split(",", 1)
                    image_data = base64.b64decode(base64_data)
                    image_buffer = io.BytesIO(image_data)

                    return StreamingResponse(
                        image_buffer,
                        media_type="image/png",
                        headers={"Content-Disposition": "inline; filename=image.png"},
                    )
                except Exception as e:
                    pass
        return FileResponse(f"{STATIC_DIR}/favicon.png")
    else:
        return FileResponse(f"{STATIC_DIR}/favicon.png")


############################
# ToggleModelById
############################


@router.post("/model/toggle", response_model=Optional[ModelResponse])
async def toggle_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if model:
        if (
            user.role == "admin"
            or model.user_id == user.id
            or has_access(user.id, "write", model.access_control)
        ):
            model = Models.toggle_model_by_id(id)

            if model:
                return model
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.UNAUTHORIZED,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateModelById
############################


@router.post("/model/update", response_model=Optional[ModelModel])
async def update_model_by_id(
    id: str,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    model = Models.get_model_by_id(id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    model = Models.update_model_by_id(id, form_data)
    return model


############################
# DeleteModelById
############################


@router.delete("/model/delete", response_model=bool)
async def delete_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        user.role != "admin"
        and model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    result = Models.delete_model_by_id(id)
    return result


@router.delete("/delete/all", response_model=bool)
async def delete_all_models(user=Depends(get_admin_user)):
    result = Models.delete_all_models()
    return result


############################
# Reindex OpenRouter Data
############################


@router.post("/reindex/openrouter")
async def reindex_openrouter(request: Request, user=Depends(get_admin_user)):
    """
    Refresh OpenRouter-backed model metadata and rebuild cached model lists.
    - Clears the OpenAI models cache keys
    - Rebuilds the in-memory BASE_MODELS/MODELS using the normal aggregation path
    """
    try:
        # Invalidate cached OpenAI model list keys (best-effort)
        try:
            cache = caches.get("default")
            await cache.delete("openai_all_models")
            await cache.delete(f"openai_all_models_{user.id}")
        except Exception:
            pass

        # Rebuild aggregated models (forces refetch of base models)
        models = await utils_get_all_models(request, refresh=True, user=user)
        return {"status": True, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BeautifyForm(BaseModel):
    icon_theme: str | None = None
    prefix: str | None = None
    allow_web_search: bool | None = None
    allow_usage_logger: bool | None = None


@router.post("/beautify/openrouter")
async def beautify_openrouter(
    request: Request,
    form_data: BeautifyForm | None = None,
    user=Depends(get_admin_user),
):
    """
    Enrich model metadata using OpenRouter's frontend models list and local icons
    (beaultifier-like). Creates/updates workspace models to persist metadata.
    """
    try:
        icon_theme = (form_data.icon_theme if form_data else None) or os.getenv(
            "IconTheme", "Transparent"
        )
        raw_prefix = (form_data.prefix if form_data else None) or os.getenv(
            "PrefixModel", "openrouter."
        )
        prefix = raw_prefix or ""
        normalized_prefix = prefix[:-1] if prefix.endswith(".") else prefix
        allow_web_search = (
            (form_data.allow_web_search if form_data else None)
            if (form_data and form_data.allow_web_search is not None)
            else (os.getenv("AllowWebSearch", "true").lower() == "true")
        )
        allow_usage_logger = (
            (form_data.allow_usage_logger if form_data else None)
            if (form_data and form_data.allow_usage_logger is not None)
            else (os.getenv("AllowUsageLogger", "true").lower() == "true")
        )

        # Fetch OpenRouter frontend models
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get("https://openrouter.ai/api/frontend/models") as r:
                r.raise_for_status()
                router_models = await r.json()

        router_map = {}
        for m in router_models.get("data", []):
            slug = (
                (m.get("endpoint", {}) or {}).get("model_variant_slug")
                or m.get("slug")
                or ""
            )
            if slug:
                router_map[slug] = m

        # Load base models and update those from OpenRouter
        base_models = await get_all_base_models(request, user=user)

        updated = 0
        failed = 0

        # Paths for icons
        repo_root = Path(__file__).resolve().parents[3]
        icons_dir = repo_root / "beaultifier" / "db" / "Icons" / icon_theme

        async def icon_to_data(author: str) -> str | None:
            try:
                path = icons_dir / f"{author}.png"
                if path.exists():
                    data = path.read_bytes()
                    return "data:image/png;base64," + base64.b64encode(data).decode()
                # Try remote fallbacks for new studios
                for url in [
                    f"https://openrouter.ai/api/author-icons/{author}.png",
                    f"https://openrouter.ai/api/assets/creators/{author}.png",
                    f"https://openrouter.ai/api/frontend/creators/{author}.png",
                ]:
                    try:
                        async with aiohttp.ClientSession(trust_env=True) as s:
                            async with s.get(url) as rr:
                                if rr.status == 200:
                                    b = await rr.read()
                                    if b:
                                        return (
                                            "data:image/png;base64," + base64.b64encode(b).decode()
                                        )
                    except Exception:
                        pass
                # Fallback: scrape author page for icon path
                try:
                    html_url = f"https://openrouter.ai/{author}"
                    async with aiohttp.ClientSession(trust_env=True) as s:
                        async with s.get(html_url) as rr:
                            if rr.status == 200:
                                html = await rr.text()
                                match = re.search(r'src=["\"](.*?images/icons/[^"\']+\.png)["\"]', html)
                                if match:
                                    icon_path = match.group(1)
                                    if icon_path.startswith("//"):
                                        icon_url = "https:" + icon_path
                                    elif icon_path.startswith("/"):
                                        icon_url = "https://openrouter.ai" + icon_path
                                    else:
                                        icon_url = icon_path
                                    async with s.get(icon_url) as icon_resp:
                                        if icon_resp.status == 200:
                                            data_bytes = await icon_resp.read()
                                            if data_bytes:
                                                return "data:image/png;base64," + base64.b64encode(data_bytes).decode()
                except Exception:
                    pass
            except Exception:
                pass
            return None

        def is_reasoning_model(rm: dict) -> bool:
            text_fields = [
                str(rm.get("slug", "")),
                str(((rm.get("endpoint") or {}).get("model_variant_slug", ""))),
                str(rm.get("name", "")),
                str(rm.get("short_name", "")),
                str(rm.get("instruct_type", "")),
                str(rm.get("group", "")),
            ]
            text = " ".join(text_fields).lower()
            if rm.get("reasoning_config") or (rm.get("features", {}) or {}).get("reasoning_config"):
                return True
            # Heuristics for models that expose reasoning but miss the flag
            keywords = [
                "think",
                "thinking",
                "reason",
                "o1",
                "o3",
                "o4",
                "gpt-5",
                "sonar-reason",
                "grok 4",
            ]
            return any(k in text for k in keywords)

        for bm in base_models:
            try:
                url_idx = bm.get("urlIdx")
                if url_idx is None:
                    continue
                base_urls = request.app.state.config.OPENAI_API_BASE_URLS
                if not base_urls or url_idx >= len(base_urls):
                    continue
                base_url = (base_urls[url_idx] or "").lower()
                if not base_url.startswith("https://openrouter.ai/api/v1"):
                    continue

                model_id = bm.get("id", "")
                slug = model_id
                for candidate in filter(None, [prefix, normalized_prefix]):
                    candidate_dot = candidate[:-1] if candidate.endswith(".") else candidate
                    options = [candidate, candidate + ".", candidate_dot + "."]
                    for opt in options:
                        if opt and model_id.startswith(opt):
                            slug = model_id[len(opt) :]
                            break
                    if slug != model_id:
                        break
                slug = slug.lstrip('.')
                router_model = router_map.get(slug)
                if not router_model:
                    continue

                # Prepare meta merging
                existing = Models.get_model_by_id(model_id)
                existing_meta = (
                    existing.meta.model_dump() if existing and existing.meta else {}
                )
                # Capabilities from existing workspace model
                existing_caps = (existing_meta.get("capabilities") or {}).copy()
                # Capabilities from base aggregated model (preserve provider flags like reasoning)
                base_caps = (
                    ((bm.get("info") or {}).get("meta") or {}).get("capabilities") or {}
                )
                for k, v in base_caps.items():
                    existing_caps.setdefault(k, v)

                # Preserve caps (from existing + base), then normalize known keys
                new_caps = existing_caps.copy()
                # Defaults that may be overridden
                new_caps["vision"] = new_caps.get("vision", False)
                new_caps["file_upload"] = new_caps.get("file_upload", False)
                new_caps["web_search"] = new_caps.get("web_search", allow_web_search)
                new_caps["image_generation"] = new_caps.get("image_generation", False)
                new_caps["code_interpreter"] = new_caps.get("code_interpreter", True)
                new_caps["citations"] = new_caps.get("citations", True)
                new_caps["usage"] = new_caps.get("usage", allow_usage_logger)

                # Infer reasoning support from OpenRouter model metadata when available
                if "reasoning" not in new_caps and is_reasoning_model(router_model):
                    new_caps["reasoning"] = True

                # Merge defaultFeatureIds: keep existing or base; if reasoning supported and none present, preserve existing array or add none (do not force-enable)
                base_default_features = (
                    ((bm.get("info") or {}).get("meta") or {}).get("defaultFeatureIds")
                )
                default_feature_ids = existing_meta.get("defaultFeatureIds") or base_default_features

                meta = {
                    **existing_meta,
                    "profile_image_url": (await icon_to_data(router_model.get("author", "")))
                    or existing_meta.get("profile_image_url")
                    or "/static/favicon.png",
                    "description": existing_meta.get("description")
                    or router_model.get("description"),
                    "suggestion_prompts": existing_meta.get("suggestion_prompts")
                    or None,
                    "tags": existing_meta.get("tags")
                    or ([{"name": router_model.get("group", "")}]
                        if router_model.get("group")
                        else existing_meta.get("tags")),
                    "capabilities": new_caps,
                    **({"defaultFeatureIds": default_feature_ids} if default_feature_ids else {}),
                }

                for cap in router_model.get("input_modalities", []) or []:
                    if cap == "image":
                        meta["capabilities"]["vision"] = True
                        meta["capabilities"]["file_upload"] = True
                    if cap == "file":
                        meta["capabilities"]["file_upload"] = True

                for cap in router_model.get("output_modalities", []) or []:
                    if cap == "image":
                        meta["capabilities"]["image_generation"] = True

                form = ModelForm(
                    id=model_id,
                    base_model_id=None,
                    name=router_model.get("name") or bm.get("name") or model_id,
                    meta=meta,
                    params={},
                    access_control=(existing.access_control if existing else {}),
                    is_active=True,
                )

                if existing:
                    Models.update_model_by_id(model_id, form)
                else:
                    Models.insert_new_model(form, user.id)
                updated += 1
            except Exception:
                failed += 1
                continue

        # Refresh aggregated list for UI
        await utils_get_all_models(request, refresh=True, user=user)
        return {"status": True, "updated": updated, "failed": failed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
