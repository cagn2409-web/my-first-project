# -*- coding: utf-8 -*-
import os
import time
import random
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from human_behavior import HumanAction
from form_gate import safe_get, ensure_register_form

try:
    import winsound
except ImportError:
    winsound = None


def _beep_alert(freq=1000, duration=300, count=3, pause=0.15):
    """Phát âm thanh cảnh báo an toàn trên Windows"""
    if not winsound:
        return
    try:
        for _ in range(count):
            winsound.Beep(freq, duration)
            time.sleep(pause)
    except Exception:
        pass


def send_telegram_alert(message, item=None):
    """Gửi thông báo qua Telegram Bot (hỗ trợ lấy token/chat_id từ item hoặc biến môi trường)"""
    try:
        token = (item and item.get('tg_token')) or os.environ.get('TG_TOKEN', 'YOUR_BOT_TOKEN')
        chat_id = (item and item.get('tg_chat_id')) or os.environ.get('TG_CHAT_ID', 'YOUR_CHAT_ID')
        if token and chat_id and token != 'YOUR_BOT_TOKEN':
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=5)
    except Exception as e:
        print(f"[Telegram Alert] Không thể gửi tin nhắn: {e}")


def dismiss_popups(driver):
    """Tự động tìm và tắt các popup thông báo, quảng cáo, xin quyền mà không chạm vào Form đăng ký"""
    try:
        js_script = """
        function closePopups() {
            let keywords = ['hủy', 'huỷ', 'đóng', 'đồng ý', 'ok', 'xác nhận', 'cho phép'];
            let els = document.querySelectorAll('button, div, span, a');

            function isFormOrInputContainer(node) {
                if (!node) return false;
                if (node.closest('form')) return true;

                let container = node.closest(
                    '.modal, .popup, .dialog, .ant-modal, .van-popup, .van-dialog, ' +
                    '.el-dialog, .el-message-box, .swal2-popup, [role="dialog"], [role="alertdialog"]'
                );
                if (!container) {
                    container = node.parentElement;
                    for (let i = 0; i < 4 && container && container.parentElement && container.parentElement !== document.body; i++) {
                        container = container.parentElement;
                    }
                }
                if (!container) return false;

                if (container.querySelector('input[type="password"]')) return true;
                let visibleInputs = Array.from(container.querySelectorAll(
                    'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"])'
                )).filter(inp => inp.offsetWidth > 20 && inp.offsetHeight > 10);

                return visibleInputs.length >= 2;
            }

            function isInsidePopupContext(node) {
                if (node.closest(
                    '.modal, .popup, .dialog, .ant-modal, .van-popup, .van-dialog, ' +
                    '.el-dialog, .el-message-box, .swal2-container, .layui-layer, ' +
                    '[role="dialog"], [role="alertdialog"], [class*="popup"], [class*="modal"], [class*="dialog"]'
                )) {
                    return true;
                }
                let curr = node;
                while (curr && curr !== document.body) {
                    let style = window.getComputedStyle(curr);
                    let zIndex = parseInt(style.zIndex, 10) || 0;
                    if ((style.position === 'fixed' || style.position === 'absolute') && zIndex >= 50) {
                        return true;
                    }
                    curr = curr.parentElement;
                }
                return false;
            }

            for (let e of els) {
                let txt = (e.innerText || e.textContent || '').trim().toLowerCase();
                if (!keywords.includes(txt) || e.offsetWidth <= 0 || e.offsetHeight <= 0) {
                    continue;
                }

                let tag = e.tagName.toLowerCase();
                let typeAttr = (e.getAttribute('type') || '').toLowerCase();
                if (tag === 'button' && typeAttr === 'submit') continue;

                if (isFormOrInputContainer(e)) continue;

                if (isInsidePopupContext(e)) {
                    try { e.click(); } catch (err) {}
                }
            }

            let hasActiveFormModal = Array.from(document.querySelectorAll(
                '.modal, .popup, .dialog, .ant-modal, .van-popup, [role="dialog"]'
            )).some(m => m.offsetWidth > 0 && m.querySelectorAll('input:not([type="hidden"])').length >= 2);

            if (!hasActiveFormModal) {
                let overlays = document.querySelectorAll('.modal-backdrop, .overlay, .ant-modal-mask, .van-overlay');
                overlays.forEach(o => o.remove());
            }
            return true;
        }
        return closePopups();
        """
        driver.execute_script(js_script)
    except Exception:
        pass


def _is_captcha_present(driver):
    """Kiểm tra Captcha chính xác (Chống báo động giả reCAPTCHA v3 & bắt cả Popup/Slider/Canvas)"""
    try:
        _captcha_check_js = """
        return (() => {
            function isVisible(el, minW = 15, minH = 10) {
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                if (rect.width < minW || rect.height < minH) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
                    return false;
                }
                let p = el.parentElement;
                while (p && p !== document.body) {
                    const pStyle = window.getComputedStyle(p);
                    if (pStyle.display === 'none' || pStyle.visibility === 'hidden' || parseFloat(pStyle.opacity) === 0) {
                        return false;
                    }
                    p = p.parentElement;
                }
                return true;
            }

            // 1. Kiểm tra Iframe Captcha (Lọc bỏ logo reCAPTCHA v3 chạy ngầm)
            const iframes = document.querySelectorAll('iframe');
            for (let ifr of iframes) {
                if (!isVisible(ifr, 30, 30)) continue;
                let src = (ifr.src || '').toLowerCase();
                let title = (ifr.title || '').toLowerCase();
                let rect = ifr.getBoundingClientRect();

                if (ifr.closest('.grecaptcha-badge') || (src.includes('anchor') && rect.width < 200)) {
                    continue;
                }
                if (src.includes('bframe') || src.includes('hcaptcha') || src.includes('turnstile') || title.includes('challenge')) {
                    return true;
                }
                if (src.includes('recaptcha') && rect.width >= 250 && rect.height >= 60) {
                    return true;
                }
            }

            // 2. Kiểm tra Captcha kéo trượt / ghép hình (Geetest, Aliyun, Slider Captcha)
            const sliders = document.querySelectorAll(
                '.geetest_panel_box, .geetest_holder, .nc-container, .slidetounlock, ' +
                '[class*="captcha-slider"], [class*="slider-captcha"], [class*="geetest"]'
            );
            for (let sl of sliders) {
                if (isVisible(sl, 100, 30)) return true;
            }

            // 3. Kiểm tra ô Input Captcha (Loại trừ ô Mã giới thiệu / Mã đại lý)
            const excludeKw = ['giới thiệu', 'gioi thieu', 'đại lý', 'dai ly', 'invite', 'refer', 'promo', 'affiliate', 'coupon'];
            const captchaKw = [
                'captcha', 'mã xác minh', 'ma xac minh', 'mã kiểm tra', 'ma kiem tra',
                'mã bảo mật', 'ma bao mat', 'security code', 'verify code', 'authcode', 'checkcode'
            ];

            const inputs = document.querySelectorAll('input:not([type="hidden"])');
            for (let inp of inputs) {
                if (!isVisible(inp, 30, 15)) continue;
                let attr = (
                    (inp.name || '') + ' ' + (inp.id || '') + ' ' +
                    (inp.placeholder || '') + ' ' + (inp.className || '') + ' ' +
                    (inp.getAttribute('aria-label') || '')
                ).toLowerCase();

                if (excludeKw.some(ex => attr.includes(ex))) continue;
                if (captchaKw.some(kw => attr.includes(kw))) return true;
            }

            // 4. Kiểm tra Hình ảnh (<img>) và Khung vẽ (<canvas>) chứa Captcha
            const visuals = document.querySelectorAll('img, canvas');
            for (let v of visuals) {
                if (!isVisible(v, 40, 18)) continue;
                let src = (v.src || '').toLowerCase();
                let alt = (v.alt || '').toLowerCase();
                let cls = (typeof v.className === 'string' ? v.className : '').toLowerCase();
                let id = (v.id || '').toLowerCase();

                if (src.includes('captcha') || alt.includes('captcha') || src.includes('securimage') || cls.includes('captcha') || id.includes('captcha')) {
                    return true;
                }
            }

            return false;
        })();
        """
        return bool(driver.execute_script(_captcha_check_js))
    except Exception:
        return False


def _handle_captcha_if_needed(driver, doctor, item, game, stage_label=""):
    """Tạm dừng an toàn, chụp ảnh, phát âm thanh và báo Telegram nếu phát hiện Captcha"""
    if not _is_captcha_present(driver):
        return False

    print(f"🚨 [AI Vision] PHÁT HIỆN CAPTCHA / MÃ XÁC MINH ({stage_label})!")
    if doctor:
        try:
            doctor.snapshot(driver, f"captcha_detected_{stage_label}")
        except Exception:
            pass

    _beep_alert(freq=1500, duration=300, count=5, pause=0.1)
    send_telegram_alert(
        f"⚠️ [BOT ALERT] Phát hiện Captcha ({stage_label}) cần giải tay cho tài khoản: {item.get('username')} | Game: {game}",
        item
    )

    print("🖐️ Bot đã tạm dừng. Vui lòng giải Captcha trên trình duyệt, sau đó nhấn [Enter] tại cửa sổ console để tiếp tục...")
    try:
        input("Nhấn [Enter] sau khi đã hoàn thành giải Captcha để bot chạy tiếp...")
    except EOFError:
        time.sleep(15)
    return True
# ==============================================================================
# KHỐI 2 (PHẦN 2): HÀM RUN_FULL_FLOW, AI VISION ĐIỀN FORM, TÍCH CHECKBOX, SUBMIT & CHECK LỖI SĐT
# ==============================================================================
def run_full_flow(driver, url, game, item, results, doctor):
    try:
        print(f"🧑‍💻 Bắt đầu: {item.get('full_name')} | {game}...")
        safe_get(driver, url)
        ensure_register_form(driver)
        time.sleep(2)
        dismiss_popups(driver)

        if doctor:
            try:
                doctor.snapshot(driver, "page_loaded")
            except Exception:
                pass

        pass_val = item.get("password") or "12345678qq"
        _v_user = str(item.get("username") or "").strip()
        _v_pass = str(pass_val).strip()
        _v_phone = str(item.get("phone_no_zero") or item.get("phone") or "").strip()
        _v_name = str(item.get("full_name") or item.get("fullname") or "").strip()
        _v_bank = str(item.get("bank_acc") or item.get("stk") or "").strip()

        # ==============================================================================
        # 1. KHỞI ĐỘNG "CON MẮT KÉP": AI DOCTOR + THỊ GIÁC DOM & TỰ ĐỘNG ĐIỀN FORM
        # ==============================================================================
        _filled_count = 0
        try:
            import time as _ai_time
            import random as _ai_random
            import threading as _ai_threading
            from selenium.webdriver.common.by import By as _AI_By
            from selenium.webdriver.common.keys import Keys as _AI_Keys
            from selenium.webdriver.common.action_chains import ActionChains as _AI_Chains

            _doc_cls = type(doctor) if doctor else object
            if not hasattr(_doc_cls, "_global_file_lock"):
                _doc_cls._global_file_lock = _ai_threading.Lock()

            print("[AI Vision] Bắt đầu quét giao diện và phân tích cấu trúc form...")

            def _count_visible_inputs(_drv):
                try:
                    return len([
                        el for el in _drv.find_elements(_AI_By.CSS_SELECTOR, "input:not([type='hidden'])")
                        if el.is_displayed() and el.is_enabled()
                    ])
                except Exception:
                    return 0

            if _count_visible_inputs(driver) < 2:
                driver.switch_to.default_content()
                for _idx, _frame in enumerate(driver.find_elements(_AI_By.TAG_NAME, "iframe")):
                    try:
                        if not _frame.is_displayed():
                            continue
                        driver.switch_to.frame(_frame)
                        if _count_visible_inputs(driver) >= 2:
                            print(f"[AI Vision] Phát hiện form trong Iframe #{_idx}, đã khóa mục tiêu.")
                            break
                        driver.switch_to.default_content()
                    except Exception:
                        driver.switch_to.default_content()

            _ai_learned = {}
            if doctor:
                try:
                    _res = doctor.learn_form_structure(driver)
                    if isinstance(_res, dict):
                        _ai_learned = _res
                    else:
                        _ai_learned = getattr(doctor, "learned_selectors", None) or getattr(doctor, "selectors", None) or {}
                except Exception as _e:
                    print(f"[AI Vision] AI Doctor tạm ngưng, chuyển sang Thị Giác DOM Nội Bộ: {_e}")

            _dom_scan_js = """
            return (() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"])'));
                const results = [];
                for (let i = 0; i < inputs.length; i++) {
                    const el = inputs[i];
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width < 20 || rect.height < 10 || style.visibility === 'hidden' || style.display === 'none' || el.disabled || el.readOnly) {
                        continue;
                    }
                    el.setAttribute('data-ai-eye-idx', String(i));
                    let contextText = '';
                    let parent = el.parentElement;
                    for (let depth = 0; depth < 3 && parent; depth++) {
                        if (parent.innerText && parent.innerText.length < 120) {
                            contextText += ' ' + parent.innerText;
                        }
                        parent = parent.parentElement;
                    }
                    results.push({
                        idx: i,
                        top: Math.round(rect.top),
                        left: Math.round(rect.left),
                        type: (el.getAttribute('type') || 'text').toLowerCase(),
                        name: (el.getAttribute('name') || '').toLowerCase(),
                        id: (el.getAttribute('id') || '').toLowerCase(),
                        placeholder: (el.getAttribute('placeholder') || '').toLowerCase(),
                        aria: (el.getAttribute('aria-label') || '').toLowerCase(),
                        auto: (el.getAttribute('autocomplete') || '').toLowerCase(),
                        context: contextText.toLowerCase().replace(/\\s+/g, ' ').trim()
                    });
                }
                results.sort((a, b) => (Math.abs(a.top - b.top) > 12 ? a.top - b.top : a.left - b.left));
                return results;
            })();
            """
            _scanned_fields = driver.execute_script(_dom_scan_js) or []
            print(f"[AI Vision] Quan sát thấy {len(_scanned_fields)} ô nhập liệu trên màn hình.")

            _classified_selectors = {}
            _used_indices = set()

            def _match_field(_role, _keywords, _exclude_kw=(), _req_type=None):
                for _item in _scanned_fields:
                    if _item["idx"] in _used_indices:
                        continue
                    if _req_type and _item["type"] != _req_type:
                        continue
                    _haystack = f"{_item['name']} {_item['id']} {_item['placeholder']} {_item['aria']} {_item['auto']} {_item['context']}"
                    if any(ex in _haystack for ex in _exclude_kw):
                        continue
                    if any(kw in _haystack for kw in _keywords):
                        _used_indices.add(_item["idx"])
                        return f"input[data-ai-eye-idx='{_item['idx']}']"
                return None

            _pass_items = [x for x in _scanned_fields if x["type"] == "password"]
            if len(_pass_items) >= 1:
                _classified_selectors["reg_password"] = f"input[data-ai-eye-idx='{_pass_items[0]['idx']}']"
                _used_indices.add(_pass_items[0]["idx"])
            if len(_pass_items) >= 2:
                _classified_selectors["reg_confirm_password"] = f"input[data-ai-eye-idx='{_pass_items[1]['idx']}']"
                _used_indices.add(_pass_items[1]["idx"])

            _cap_sel = _match_field(
                "reg_captcha",
                ["captcha", "ma xac minh", "mã xác minh", "mã kiểm tra", "ma kiem tra", "verify code", "security code", "authcode", "checkcode"],
                _exclude_kw=["giới thiệu", "gioi thieu", "đại lý", "dai ly", "invite", "refer", "promo", "affiliate", "coupon"]
            )
            if _cap_sel:
                _classified_selectors["reg_captcha"] = _cap_sel

            _phone_sel = _match_field("reg_phone", ["phone", "mobile", "sdt", "sđt", "điện thoại", "dien thoai", "tel", "zalo", "số đt"])
            if _phone_sel:
                _classified_selectors["reg_phone"] = _phone_sel

            _bank_sel = _match_field("reg_bank", ["bank", "stk", "ngân hàng", "ngan hang", "số tài khoản", "so tai khoan", "card", "account number", "tk ngân hàng"])
            if _bank_sel:
                _classified_selectors["reg_bank"] = _bank_sel

            _name_sel = _match_field(
                "reg_fullname",
                ["fullname", "full_name", "realname", "real_name", "họ và tên", "ho va ten", "họ tên", "ho ten", "tên thật", "ten that", "chủ tài khoản", "chu tai khoan", "payee"],
                _exclude_kw=["đăng nhập", "dang nhap", "user", "account"]
            )
            if _name_sel:
                _classified_selectors["reg_fullname"] = _name_sel

            _user_sel = _match_field(
                "reg_username",
                ["user", "username", "account", "login", "tên đăng nhập", "ten dang nhap", "tài khoản", "tai khoan", "id đăng nhập", "member"],
                _exclude_kw=["ngân hàng", "ngan hang", "bank", "chủ tài khoản", "họ tên"]
            )
            if not _user_sel:
                _first_text = next((x for x in _scanned_fields if x["idx"] not in _used_indices and x["type"] in ("text", "email", "")), None)
                if _first_text:
                    _user_sel = f"input[data-ai-eye-idx='{_first_text['idx']}']"
                    _used_indices.add(_first_text["idx"])
            if _user_sel:
                _classified_selectors["reg_username"] = _user_sel

            _key_map = {
                "reg_username": ["username_input", "username", "user_input", "account_input"],
                "reg_password": ["password_input", "password", "pass_input"],
                "reg_confirm_password": ["confirm_password_input", "confirm_password", "repass_input"],
                "reg_phone": ["phone_input", "phone", "mobile_input", "tel_input"],
                "reg_fullname": ["fullname_input", "fullname", "name_input", "realname_input"],
                "reg_bank": ["bank_input", "bank_account", "stk_input", "bank_number"],
                "reg_captcha": ["captcha_input", "captcha", "verify_code_input"]
            }

            if isinstance(_ai_learned, dict):
                for _k, _css in _ai_learned.items():
                    if not _css or not isinstance(_css, str):
                        continue
                    try:
                        _els = driver.find_elements(_AI_By.CSS_SELECTOR, _css)
                        if any(e.is_displayed() and e.is_enabled() for e in _els):
                            _classified_selectors.setdefault(_k, _css)
                    except Exception:
                        pass

            _final_selectors = {}
            for _main_k, _sel_val in _classified_selectors.items():
                _final_selectors[_main_k] = _sel_val
                for _alias in _key_map.get(_main_k, []):
                    _final_selectors[_alias] = _sel_val

            if doctor and hasattr(doctor, "selectors") and isinstance(doctor.selectors, dict):
                doctor.selectors.update(_final_selectors)

            print(f"[AI Vision] Đã khóa chính xác các trường: {list(_classified_selectors.keys())}")

            def _eye_human_fill(_drv, _css_selector, _text_value, _label_name=""):
                if not _css_selector or not _text_value:
                    return False
                try:
                    _candidates = _drv.find_elements(_AI_By.CSS_SELECTOR, _css_selector)
                    _target = next((e for e in _candidates if e.is_displayed() and e.is_enabled()), None)
                    if not _target:
                        return False

                    _drv.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", _target)
                    _ai_time.sleep(_ai_random.uniform(0.25, 0.45))

                    try:
                        _AI_Chains(_drv).move_to_element_with_offset(
                            _target, _ai_random.randint(-3, 3), _ai_random.randint(-2, 2)
                        ).pause(_ai_random.uniform(0.08, 0.18)).click().perform()
                    except Exception:
                        _drv.execute_script("arguments[0].focus(); arguments[0].click();", _target)

                    _ai_time.sleep(_ai_random.uniform(0.1, 0.25))

                    _existing_val = _target.get_attribute("value") or ""
                    if _existing_val:
                        _target.send_keys(_AI_Keys.CONTROL + "a")
                        _ai_time.sleep(0.08)
                        _target.send_keys(_AI_Keys.BACKSPACE)
                        _ai_time.sleep(0.1)

                    for _ch in str(_text_value):
                        _target.send_keys(_ch)
                        _ai_time.sleep(_ai_random.uniform(0.04, 0.11))

                    _after_val = _target.get_attribute("value") or ""
                    if str(_text_value).strip() not in _after_val:
                        _js_react_set = """
                        const el = arguments[0];
                        const val = arguments[1];
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        if (setter) setter.call(el, val); else el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        """
                        _drv.execute_script(_js_react_set, _target, str(_text_value))

                    _ai_time.sleep(_ai_random.uniform(0.35, 0.75))
                    print(f"[AI Vision] -> Đã điền chính xác [{_label_name}]")
                    return True
                except Exception as _fill_err:
                    print(f"[AI Vision] -> Lỗi khi điền [{_label_name}]: {_fill_err}")
                    return False

            _step_plan = [
                ("Tai khoan (Username)", _classified_selectors.get("reg_username"), _v_user),
                ("Mat khau (Password)", _classified_selectors.get("reg_password"), _v_pass),
                ("Xac nhan MK (Confirm)", _classified_selectors.get("reg_confirm_password"), _v_pass),
                ("Ho va ten (Fullname)", _classified_selectors.get("reg_fullname"), _v_name),
                ("So dien thoai (Phone)", _classified_selectors.get("reg_phone"), _v_phone),
                ("So tai khoan (Bank)", _classified_selectors.get("reg_bank"), _v_bank),
            ]

            for _label, _sel, _val in _step_plan:
                if _sel and _val:
                    if _eye_human_fill(driver, _sel, _val, _label):
                        _filled_count += 1

            print(f"[AI Vision] Hoàn tất điền {_filled_count} trường trên form! Giác quan sẵn sàng.")

        except Exception as _vision_exc:
            print(f"[AI Vision] Cảnh báo hệ thống quan sát: {type(_vision_exc).__name__}: {_vision_exc}")
            _filled_count = 0

        # ==============================================================================
        # 2. LỚP DỰ PHÒNG JS & AI DOCTOR (NẾU AI VISION KHÔNG TÌM THẤY TRƯỜNG)
        # ==============================================================================
        filled = []
        if _filled_count == 0:
            print("⚠️ AI Vision không tìm thấy trường, đang kích hoạt JS dự phòng...")
            js_fill = """
            const userVal = arguments[0], passVal = arguments[1], nameVal = arguments[2], phoneNoZero = arguments[3], bankAcc = arguments[4];
            let filled = [];
            function setVal(el, val, fieldName) {
                if (!el || !val) return false;
                try {
                    el.focus();
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    if (setter) setter.call(el, val); else el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    filled.push(fieldName);
                    return true;
                } catch(e) { return false; }
            }
            Array.from(document.querySelectorAll('input')).filter(i => i.getBoundingClientRect().width > 40 && !['checkbox', 'hidden', 'submit'].includes(i.type)).forEach((inp) => {
                let h = (inp.name + ' ' + inp.id + ' ' + inp.placeholder).toLowerCase();
                if (inp.type === 'password' || h.includes('pass') || h.includes('mật khẩu')) { setVal(inp, passVal, 'password'); }
                else if (h.includes('tên') || h.includes('fullname') || h.includes('realname')) { setVal(inp, nameVal, 'fullname'); }
                else if (h.includes('điện thoại') || h.includes('phone') || h.includes('tel') || h.includes('sđt')) { setVal(inp, phoneNoZero, 'phone'); }
                else if (h.includes('ngân hàng') || h.includes('stk') || h.includes('bank')) { setVal(inp, bankAcc, 'bank'); }
                else if (h.includes('tài khoản') || h.includes('account') || h.includes('user') || h.includes('login')) { setVal(inp, userVal, 'username'); }
            });
            return filled;
            """
            time.sleep(random.uniform(1.5, 3.0))
            try:
                filled = driver.execute_script(js_fill, _v_user, _v_pass, _v_name, _v_phone, _v_bank) or []
            except Exception:
                pass
            print(f"🧑‍💻 Đã điền bằng JS dự phòng: {filled}")
        else:
            filled = ["username", "password"]
            print("✅ AI Vision đã điền form thành công, bỏ qua JS dự phòng.")

        if "username" not in filled or "password" not in filled:
            print("🧑‍💻 Dùng AI Doctor tìm ô nhập...")
            try:
                if doctor:
                    el = doctor.find(driver, "username_input", fallback="input[name='username']")
                    if el and _v_user:
                        HumanAction.human_type(driver, el, _v_user)
                    el = doctor.find(driver, "password_input", fallback="input[type='password']")
                    if el and _v_pass:
                        HumanAction.human_type(driver, el, _v_pass)
            except Exception as e:
                print(f"⚠️ AI Doctor: {e}")

        # ==============================================================================
        # 3. TÍCH CHECKBOX ĐIỀU KHOẢN & KIỂM TRA CAPTCHA TRƯỚC KHI BẤM ĐĂNG KÝ
        # ==============================================================================
        try:
            _tick_checkbox_js = """
            let ticked = 0;
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                const rect = cb.getBoundingClientRect();
                if (!cb.checked && (rect.width > 0 || cb.offsetParent !== null)) {
                    cb.click();
                    ticked++;
                }
            });
            document.querySelectorAll(
                '.ant-checkbox:not(.ant-checkbox-checked), ' +
                '.el-checkbox:not(.is-checked), ' +
                '.van-checkbox[aria-checked="false"]'
            ).forEach(customCb => {
                if (customCb.offsetWidth > 0) {
                    customCb.click();
                    ticked++;
                }
            });
            return ticked;
            """
            _ticked_count = driver.execute_script(_tick_checkbox_js)
            if _ticked_count:
                print(f"☑️ Đã tự động tích {_ticked_count} ô đồng ý điều khoản / xác nhận tuổi.")
        except Exception:
            pass

        _handle_captcha_if_needed(driver, doctor, item, game, stage_label="form_dang_ky")

        # ==============================================================================
        # 4. BẤM NÚT ĐĂNG KÝ (SUBMIT) & KIỂM TRA LỖI TỒN TẠI DỮ LIỆU
        # ==============================================================================
        _reg_submitted = False
        try:
            print("[AI Submit] Đang tìm nút gửi biểu mẫu Đăng ký...")
            _submit_candidates = driver.find_elements(
                By.XPATH,
                "//button[@type='submit'] | //input[@type='submit'] | "
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZĐ', 'abcdefghijklmnopqrstuvwxyzđ'), 'đăng ký') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'dang ky') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'register') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'hoàn tất') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'xác nhận') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tham gia')] | "
                "//div[@role='button' or contains(@class, 'btn') or contains(@class, 'submit')]"
                "[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZĐ', 'abcdefghijklmnopqrstuvwxyzđ'), 'đăng ký') or "
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'register')]"
            )

            for _btn in _submit_candidates:
                try:
                    if not _btn.is_displayed() or not _btn.is_enabled():
                        continue
                    _btn_txt = (_btn.text or _btn.get_attribute("value") or "").strip().lower()
                    if any(bad in _btn_txt for bad in ["đăng nhập", "dang nhap", "login", "hủy", "huỷ", "đóng", "close", "quên"]):
                        continue
                    if len(_btn_txt) > 35:
                        continue

                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", _btn)
                    time.sleep(random.uniform(0.3, 0.6))
                    try:
                        ActionChains(driver).move_to_element(_btn).pause(random.uniform(0.15, 0.35)).click().perform()
                    except Exception:
                        driver.execute_script("arguments[0].click();", _btn)

                    print(f"🚀 [AI Submit] Đã bấm nút Đăng ký: '{_btn_txt or 'Submit'}'")
                    _reg_submitted = True
                    break
                except Exception:
                    continue
        except Exception as _sub_err:
            print(f"⚠️ [AI Submit] Lỗi khi tìm/bấm nút Đăng ký: {_sub_err}")

        if _reg_submitted:
            time.sleep(random.uniform(2.5, 4.0))
            
            _handle_captcha_if_needed(driver, doctor, item, game, stage_label="sau_khi_bam_dang_ky")

            try:
                driver.switch_to.default_content()
            except Exception:
                pass

            # Quét thông báo lỗi trùng SĐT / Tài khoản
            _verify_reg_js = """
            return (() => {
                const bodyText = (document.body.innerText || '').toLowerCase();
                const alertElements = document.querySelectorAll('.el-message, .ant-message, .van-toast, .alert, .error, [class*="error"], [class*="tip"]');
                let alertText = '';
                alertElements.forEach(el => { alertText += ' ' + (el.innerText || '').toLowerCase(); });
                
                const fullCheckText = bodyText + ' ' + alertText;

                const errorKeywords = [
                    'đã tồn tại', 'da ton tai', 'đã được sử dụng', 'da duoc su dung',
                    'already exists', 'already registered', 'tài khoản đã có', 'tài khoản đã tồn tại',
                    'số điện thoại đã', 'sdt da', 'phone already', 'phone exists', 'registered', 'exist'
                ];
                
                for (let kw of errorKeywords) {
                    if (fullCheckText.includes(kw)) {
                        return { status: 'PHONE_EXISTS', detail: kw };
                    }
                }
                return { status: 'OK', detail: '' };
            })();
            """
            try:
                _reg_check = driver.execute_script(_verify_reg_js) or {}
                if _reg_check.get("status") == "PHONE_EXISTS":
                    err_reason = _reg_check.get('detail', 'SĐT/Tài khoản đã tồn tại')
                    print(f"❌ [AI Submit] PHÁT HIỆN LỖI ĐĂNG KÝ: '{err_reason}'")
                    
                    if doctor:
                        try:
                            doctor.snapshot(driver, "register_error_phone_exists")
                        except Exception:
                            pass
                    
                    _beep_alert(freq=1400, duration=300, count=4, pause=0.1)
                    error_msg = f"❌ [BOT ERROR] Đăng ký thất bại (Trùng SĐT/TK): {item.get('username')} ({item.get('full_name')}) | Lý do: {err_reason} | Game: {game}"
                    send_telegram_alert(error_msg, item)
                    
                    print("🛑 Bot dừng luồng của tài khoản này do lỗi tồn tại dữ liệu và đã báo cáo về Telegram.")
                    return "PHONE_EXISTS"
            except Exception as _err_chk:
                print(f"⚠️ Lỗi khi quét trạng thái phản hồi đăng ký: {_err_chk}")

            dismiss_popups(driver)
            time.sleep(random.uniform(0.8, 1.5))

            # Tự động tìm và bấm vào mục "Rút tiền" / "Liên kết ngân hàng" để mở màn hình cho Khối 3
            try:
                _withdraw_nav_xpath = (
                    "//*[self::a or self::button or self::div or self::span]"
                    "[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZĐ', 'abcdefghijklmnopqrstuvwxyzđ'), 'rút tiền') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'rut tien') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'withdraw') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'thêm ngân hàng') or "
                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'liên kết ngân hàng')]"
                )
                for _nav in driver.find_elements(By.XPATH, _withdraw_nav_xpath):
                    if _nav.is_displayed() and 0 < len((_nav.text or "").strip()) < 25:
                        print(f"[AI Navigation] -> Đang bấm mở mục '{_nav.text.strip()}' để cài đặt ngân hàng...")
                        try:
                            ActionChains(driver).move_to_element(_nav).pause(random.uniform(0.15, 0.3)).click().perform()
                        except Exception:
                            driver.execute_script("arguments[0].click();", _nav)
                        time.sleep(random.uniform(1.5, 2.5))
                        break
            except Exception:
                pass
        # ==============================================================================
        # LUỒNG BỔ SUNG TỐI ƯU TOÀN DIỆN: MẬT KHẨU RÚT TIỀN & LIÊN KẾT NGÂN HÀNG
        # ==============================================================================
        try:
            import time as _b_time
            import random as _b_random
            from selenium.webdriver.common.by import By as _B_By
            from selenium.webdriver.common.action_chains import ActionChains as _B_Chains

            try:
                driver.switch_to.default_content()
            except Exception:
                pass

            _b_time.sleep(_b_random.uniform(1.0, 2.0))
            print("[AI Banking] Đang quét giao diện liên kết ngân hàng & mật khẩu rút tiền...")

            _withdrawal_pass = str(item.get('withdrawal_pass') or _v_pass).strip()
            _bank_name_target = str(item.get('bank_name') or 'Techcombank').strip()
            _branch_name = str(item.get('branch') or 'Hà Nội').strip()

            _bank_scan_js = """
            return (() => {
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"])'));
                const results = [];
                for (let i = 0; i < inputs.length; i++) {
                    const el = inputs[i];
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width < 20 || rect.height < 10 || style.display === 'none' || style.visibility === 'hidden' || el.disabled || el.readOnly) continue;
                    el.setAttribute('data-ai-bank-idx', String(i));
                    let ctx = '';
                    let p = el.parentElement;
                    for (let d = 0; d < 3 && p; d++) {
                        if (p.innerText && p.innerText.length < 100) ctx += ' ' + p.innerText;
                        p = p.parentElement;
                    }
                    results.push({
                        idx: i,
                        type: (el.getAttribute('type') || 'text').toLowerCase(),
                        name: (el.getAttribute('name') || '').toLowerCase(),
                        placeholder: (el.getAttribute('placeholder') || '').toLowerCase(),
                        context: ctx.toLowerCase().replace(/\\s+/g, ' ').trim(),
                        hasVal: Boolean((el.value || '').trim())
                    });
                }
                return results;
            })();
            """
            _bank_fields = driver.execute_script(_bank_scan_js) or []

            def _safe_human_type(el, text, label):
                if not text:
                    return False
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", el)
                    _b_time.sleep(_b_random.uniform(0.3, 0.6))

                    try:
                        _B_Chains(driver).move_to_element(el).click().perform()
                    except Exception:
                        driver.execute_script("arguments[0].focus(); arguments[0].click();", el)

                    _b_time.sleep(_b_random.uniform(0.15, 0.35))

                    if el.get_attribute("value"):
                        el.send_keys(Keys.CONTROL + "a")
                        _b_time.sleep(0.08)
                        el.send_keys(Keys.BACKSPACE)
                        _b_time.sleep(0.1)

                    for ch in str(text):
                        el.send_keys(ch)
                        _b_time.sleep(_b_random.uniform(0.05, 0.14))

                    _after = el.get_attribute("value") or ""
                    if str(text).strip() not in _after:
                        _js_sync = """
                        const el = arguments[0], val = arguments[1];
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        if (setter) setter.call(el, val); else el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        """
                        driver.execute_script(_js_sync, el, str(text))

                    print(f"[AI Banking] -> Đã điền: {label}")
                    _b_time.sleep(_b_random.uniform(0.3, 0.5))
                    return True
                except Exception as e:
                    print(f"[AI Banking] -> Lỗi điền {label}: {e}")
                    return False

            for _f in _bank_fields:
                _hay = f"{_f['name']} {_f['placeholder']} {_f['context']}"
                try:
                    _target_el = driver.find_element(_B_By.CSS_SELECTOR, f"input[data-ai-bank-idx='{_f['idx']}']")
                    if not _target_el.is_displayed():
                        continue

                    # 1. Điền Mật khẩu rút tiền / Mã PIN
                    if any(kw in _hay for kw in ['mật khẩu rút', 'mat khau rut', 'fund password', 'pin', 'mã pin', 'withdrawal password', 'payment password', 'mật khẩu giao dịch']):
                        _safe_human_type(_target_el, _withdrawal_pass, "Mật khẩu rút tiền")

                    # 2. Điền Chi nhánh ngân hàng
                    elif any(kw in _hay for kw in ['chi nhánh', 'chi nhanh', 'branch', 'tỉnh thành', 'phòng giao dịch', 'city', 'province']):
                        _safe_human_type(_target_el, _branch_name, f"Chi nhánh ({_branch_name})")

                    # 3. Điền bổ sung Số tài khoản nếu chưa có
                    elif not _f['hasVal'] and any(kw in _hay for kw in ['số tài khoản', 'so tai khoan', 'stk', 'account number', 'bank account', 'số thẻ']):
                        _safe_human_type(_target_el, _v_bank, "Số tài khoản ngân hàng")

                    # 4. Điền bổ sung Chủ tài khoản nếu chưa có
                    elif not _f['hasVal'] and any(kw in _hay for kw in ['chủ tài khoản', 'chu tai khoan', 'tên chủ thẻ', 'account holder', 'payee']):
                        _safe_human_type(_target_el, _v_name, "Chủ tài khoản")
                except Exception:
                    continue

            # Xử lý Dropdown chọn Ngân hàng
            _dropdown_xpath = (
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'chọn ngân hàng') or "
                "contains(translate(text(), '
