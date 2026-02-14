import locale

_current_locale: str = "fr"

_STRINGS: dict[str, dict[str, str]] = {
    "app_title": {
        "fr": "Compresseur Vidéo",
        "en": "Video Compressor",
    },
    "source_video": {
        "fr": "Vidéo source",
        "en": "Source video",
    },
    "choose": {
        "fr": "Choisir...",
        "en": "Browse...",
    },
    "choose_video": {
        "fr": "Choisir une vidéo",
        "en": "Choose a video",
    },
    "compression_settings": {
        "fr": "Paramètres de compression",
        "en": "Compression settings",
    },
    "resolution": {
        "fr": "Résolution",
        "en": "Resolution",
    },
    "video_kbps": {
        "fr": "Vidéo kb/s",
        "en": "Video kb/s",
    },
    "keep_audio": {
        "fr": "Garder l'audio",
        "en": "Keep audio",
    },
    "format": {
        "fr": "Format",
        "en": "Format",
    },
    "gif_hint": {
        "fr": "Pour GIF, le débit vidéo est ignoré; ajustez Résolution/FPS.",
        "en": "For GIF, video bitrate is ignored; adjust Resolution/FPS.",
    },
    "estimate_prefix": {
        "fr": "Estimation taille maximale",
        "en": "Estimated max size",
    },
    "compress": {
        "fr": "Compresser",
        "en": "Compress",
    },
    "cancel": {
        "fr": "Annuler",
        "en": "Cancel",
    },
    "compressing": {
        "fr": "Compression en cours…",
        "en": "Compressing…",
    },
    "compressing_detail": {
        "fr": "Compression en cours… Cela peut prendre un moment.",
        "en": "Compressing… This may take a while.",
    },
    "confirmation": {
        "fr": "Confirmation",
        "en": "Confirmation",
    },
    "confirm_size": {
        "fr": "Taille maximale estimée: {size}\n\nContinuer ?",
        "en": "Estimated max size: {size}\n\nContinue?",
    },
    "done_title": {
        "fr": "Terminé",
        "en": "Done",
    },
    "done_message": {
        "fr": "Compression terminée.\nFichier: {path}\nTaille: {size}\n\nOuvrir le dossier ?",
        "en": "Compression complete.\nFile: {path}\nSize: {size}\n\nOpen folder?",
    },
    "error": {
        "fr": "Erreur",
        "en": "Error",
    },
    "fail_title": {
        "fr": "Échec",
        "en": "Failed",
    },
    "fail_message": {
        "fr": "La compression a échoué.\n\n{details}",
        "en": "Compression failed.\n\n{details}",
    },
    "cancelled_title": {
        "fr": "Annulé",
        "en": "Cancelled",
    },
    "cancelled_message": {
        "fr": "La compression a été annulée.",
        "en": "Compression was cancelled.",
    },
    "file_not_found": {
        "fr": "Fichier introuvable",
        "en": "File not found",
    },
    "select_valid_video": {
        "fr": "Veuillez sélectionner une vidéo valide.",
        "en": "Please select a valid video.",
    },
    "analysis_error": {
        "fr": "Erreur d'analyse",
        "en": "Analysis error",
    },
    "invalid_location": {
        "fr": "Emplacement invalide",
        "en": "Invalid location",
    },
    "cannot_write": {
        "fr": "Impossible d'écrire dans le dossier source ou Téléchargements.",
        "en": "Cannot write to source folder or Downloads.",
    },
    "ffmpeg_missing_title": {
        "fr": "FFmpeg manquant",
        "en": "FFmpeg missing",
    },
    "disk_space_title": {
        "fr": "Espace disque insuffisant",
        "en": "Insufficient disk space",
    },
    "disk_space_message": {
        "fr": "L'espace disque disponible semble insuffisant pour le fichier estimé.\n\nContinuer quand même ?",
        "en": "Available disk space seems insufficient for the estimated file.\n\nContinue anyway?",
    },
    "videos_filter": {
        "fr": "Vidéos",
        "en": "Videos",
    },
    "all_files_filter": {
        "fr": "Tous les fichiers",
        "en": "All files",
    },
}


def detect_locale() -> str:
    try:
        loc = locale.getdefaultlocale()[0] or ""
    except Exception:
        loc = ""
    return "en" if loc.startswith("en") else "fr"


def set_locale(lang: str) -> None:
    global _current_locale
    _current_locale = lang


def get_locale() -> str:
    return _current_locale


def t(key: str, **kwargs: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_locale, entry.get("fr", key))
    if kwargs:
        text = text.format(**kwargs)
    return text


# Auto-detect on import
set_locale(detect_locale())
