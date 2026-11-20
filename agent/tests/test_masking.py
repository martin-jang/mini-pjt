import logging

from legacy2next.masking import MASK, SecretMaskingFilter, SecretRegistry


def test_mask_replaces_all_registered_values_longest_first():
    reg = SecretRegistry()
    reg.register("abc", "abcdef", None, "x")  # 짧은 값과 None은 무시
    assert reg.mask("id=abcdef pw=abc x") == f"id={MASK} pw={MASK} x"


def test_logging_filter_masks_formatted_message(caplog):
    reg = SecretRegistry()
    reg.register("pw-secret")
    logger = logging.getLogger("test.masking")
    logger.addFilter(SecretMaskingFilter(reg))
    with caplog.at_level(logging.INFO, logger="test.masking"):
        logger.info("로그인 시도: %s", "pw-secret")
    assert "pw-secret" not in caplog.text
    assert MASK in caplog.text
