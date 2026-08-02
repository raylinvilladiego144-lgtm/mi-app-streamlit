"""
app/security/passwords.py

Funciones para generar y verificar hashes de contraseñas.
"""

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


def hash_password(password: str) -> str:
    """
    Genera el hash de una contraseña.
    """

    return generate_password_hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Verifica una contraseña contra su hash.
    """

    return check_password_hash(
        password_hash,
        password,
    )