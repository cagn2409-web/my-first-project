import winsound
import requests
import os

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
# -*- coding: utf-8 -*-
import time, random
from selenium.webdriver.common.by import By
from human_behavior import HumanAction
from form_gate import safe_get, ensure_register_form


def dismiss_popups(driver):
    """Tự động tìm và tắt các popup thông báo, quảng cáo, xin quyền"""
    try:
        js_script = """
        function closePopups() {
            // 1. Tìm các nút có chữ Hủy, Đóng, Đồng ý, X
            let keywords = ['hủy', 'huỷ', 'đóng', 'đồng ý', 'ok', 'xác nhận', 'cho phép'];
            let els = document.querySelectorAll('button, div, span, a');
            for (let e of els) {
                let txt = (e.innerText || '').trim().toLowerCase();
                if (keywords.includes(txt) && e.offsetWidth > 0) {
                    e.click();
                }
            }
            // 2. Xóa các lớp overlay che màn hình
            let overlays = document.querySelectorAll('.modal-backdrop, .overlay, .ant-modal-mask, .van-overlay');
            overlays.forEach(o => o.remove());
            return true;
        }
        return closePopups();
        """
        driver.execute_script(js_script)
    except:
        pass

def run_full_flow(driver, url, game, item, results, doctor):
    try:
        print(f"🧑‍💻 Bắt đầu: {item.get('full_name')} | {game}...")
        safe_get(driver, url)
        ensure_register_form(driver)
        time.sleep(2)
        dismiss_popups(driver)
        
        if doctor:
            doctor.snapshot(driver, "page_loaded")

        pass_val = "12345678qq"
        
        # ==============================================================================
        # KHOI DONG "CON MAT KEP": AI DOCTOR + THI GIAC DOM THUC TE & TU DONG DIEN FORM
        # ==============================================================================
        try:
            import json as _ai_json
            import os as _ai_os
            import time as _ai_time
            import random as _ai_random
            import threading as _ai_threading
            from selenium.webdriver.common.by import By as _AI_By
            from selenium.webdriver.common.keys import Keys as _AI_Keys
            from selenium.webdriver.common.action_chains import ActionChains as _AI_Chains

            _doc_cls = type(doctor) if doctor else object
            if not hasattr(_doc_cls, "_global_file_lock"):
                _doc_cls._global_file_lock = _ai_threading.Lock()

            print("[AI Vision] Bat dau quet giao dien va phan tich cau truc form...")

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
                            print(f"[AI Vision] Phat hien form trong Iframe #{_idx}, da khoa muc tieu.")
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
                    print(f"[AI Vision] AI Doctor tam ngung, chuyen sang Thi Giac DOM Noi Bo: {_e}")

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
            print(f"[AI Vision] Quan sat thay {len(_scanned_fields)} o nhap lieu tren man hinh.")

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

            _cap_sel = _match_field("reg_captcha", ["captcha", "ma xac", "mã xác", "xac minh", "xác minh", "verify", "code", "otp"])
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

            for _dict_name in ("selectors", "form_selectors", "custom_selectors", "learned_selectors"):
                if _dict_name in locals() and isinstance(locals()[_dict_name], dict):
                    locals()[_dict_name].update(_final_selectors)
            if doctor and hasattr(doctor, "selectors") and isinstance(doctor.selectors, dict):
                doctor.selectors.update(_final_selectors)

            print(f"[AI Vision] Da khoa chinh xac cac truong: {list(_classified_selectors.keys())}")

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
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        """
                        _drv.execute_script(_js_react_set, _target, str(_text_value))

                    _ai_time.sleep(_ai_random.uniform(0.35, 0.75))
                    print(f"[AI Vision] -> Da dien chinh xac [{_label_name}]")
                    return True
                except Exception as _fill_err:
                    print(f"[AI Vision] -> Loi khi dien [{_label_name}]: {_fill_err}")
                    return False

            _loc = locals()
            def _resolve_val(*_names):
                for _n in _names:
                    if _n in _loc and _loc[_n] is not None and str(_loc[_n]).strip() != "":
                        return str(_loc[_n]).strip()
                    for _dict_k in ("data", "user_data", "account", "info", "payload", "customer", "item"):
                        if _dict_k in _loc and isinstance(_loc[_dict_k], dict):
                            if _loc[_dict_k].get(_n):
                                return str(_loc[_dict_k][_n]).strip()
                return None

            _v_user = _resolve_val("username", "user_val", "acc_val", "account", "tk", "user", "ten_tk")
            _v_pass = _resolve_val("pass_val", "password", "pwd", "mat_khau") or pass_val
            _v_phone = _resolve_val("phone", "phone_val", "sdt", "so_dien_thoai", "mobile", "tel", "phone_no_zero")
            _v_name = _resolve_val("fullname", "name_val", "full_name", "ho_ten", "ten_that", "realname", "name")
            _v_bank = _resolve_val("stk", "bank_account", "bank_val", "so_tai_khoan", "bank_number", "account_number", "bank_acc")

            _step_plan = [
                ("Tai khoan (Username)", _classified_selectors.get("reg_username"), _v_user),
                ("Mat khau (Password)", _classified_selectors.get("reg_password"), _v_pass),
                ("Xac nhan MK (Confirm)", _classified_selectors.get("reg_confirm_password"), _v_pass),
                ("Ho va ten (Fullname)", _classified_selectors.get("reg_fullname"), _v_name),
                ("So dien thoai (Phone)", _classified_selectors.get("reg_phone"), _v_phone),
                ("So tai khoan (Bank)", _classified_selectors.get("reg_bank"), _v_bank),
            ]        _filled_count = 0
        for _label, _sel, _val in _step_plan:
            if _sel and _val:
                if _eye_human_fill(driver, _sel, _val, _label):
                    _filled_count += 1

        print(f"[AI Vision] Hoan tat dien {_filled_count} truong tren form! Giac quan san sang.")

    except Exception as _vision_exc:
        print(f"[AI Vision] Canh bao he thong quan sat: {type(_vision_exc).__name__}: {_vision_exc}")
        _filled_count = 0  # Đảm bảo gán về 0 nếu AI Vision lỗi để kích hoạt fallback
    # ==============================================================================
    
    # Khởi tạo biến filled để tránh lỗi NameError ở các bước sau
    filled = []
    
    # Chỉ dùng JS Fill nếu AI Vision không điền được (đề phòng AI Vision lỗi hoặc form quá lạ)
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
        document.querySelectorAll('input[type="checkbox"]').forEach(cb => { 
            let h = (cb.name + ' ' + cb.id + ' ' + cb.className).toLowerCase();
            if ((h.includes('term') || h.includes('agree') || h.includes('điều khoản') || h.includes('đồng ý')) && !cb.checked) cb.click(); 
        });
        return filled;
        """
        
        time.sleep(random.uniform(1.5, 3.0)) # Human-like Delay trước khi điền form
        try: 
            filled = driver.execute_script(js_fill, item['username'], pass_val, item['full_name'], item['phone_no_zero'], item['bank_acc']) or []
        except: 
            pass
        print(f"🧑‍💻 Đã điền bằng JS dự phòng: {filled}")
    else:
        # Nếu AI Vision đã điền thành công, ta đánh dấu ảo để bỏ qua bước check bên dưới
        filled = ["username", "password"] 
        print("✅ AI Vision đã điền form thành công, bỏ qua JS dự phòng.")

    # Fallback cuối cùng: Dùng AI Doctor nếu cả 2 cách trên đều thất bại
    if "username" not in filled or "password" not in filled:
        print("🧑‍💻 Dùng AI Doctor tìm ô nhập...")
        try:
            el = doctor.find(driver, "username_input", fallback="input[name='username']")
            if el: HumanAction.human_type(driver, el, item['username'])
            el = doctor.find(driver, "password_input", fallback="input[type='password']")
            if el: HumanAction.human_type(driver, el, pass_val)
        except Exception as e: 
            print(f"⚠️ AI Doctor: {e}")
        
        # ==============================================================================
    # 1. LUỒNG MẬT KHẨU RÚT TIỀN & LIÊN KẾT NGÂN HÀNG (TÍCH HỢP ACTIONCHAINS)
    # ==============================================================================
    try:
        import time as _b_time
        import random as _b_random
        from selenium.webdriver.common.by import By as _B_By
        from selenium.webdriver.common.action_chains import ActionChains

        try:
            driver.switch_to.default_content()
        except Exception:
            pass

        _b_time.sleep(_b_random.uniform(1.0, 2.0))
        print("[AI Banking] Đang quét giao diện liên kết ngân hàng & mật khẩu rút tiền...")

        _bank_scan_js = """
        return (() => {
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])'));
            const results = [];
            for (let i = 0; i < inputs.length; i++) {
                const el = inputs[i];
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width < 20 || rect.height < 10 || style.display === 'none' || el.disabled) continue;
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
                    context: ctx.toLowerCase().replace(/\\s+/g, ' ').trim()
                });
            }
            return results;
        })();
        """
        _bank_fields = driver.execute_script(_bank_scan_js) or []
        
        _withdrawal_pass = item.get('withdrawal_pass') or pass_val
        _bank_name_target = item.get('bank_name', 'Techcombank')
        _branch_name = item.get('branch', 'Hà Nội')

        for _f in _bank_fields:
            _hay = f"{_f['name']} {_f['placeholder']} {_f['context']}"
            try:
                _target_el = driver.find_element(_B_By.CSS_SELECTOR, f"input[data-ai-bank-idx='{_f['idx']}']")
                if not _target_el.is_displayed():
                    continue
                
                if any(kw in _hay for kw in ['mật khẩu rút', 'mat khau rut', 'fund password', 'pin', 'mã pin', 'withdrawal password', 'payment password']):
                    print(f"[AI Banking] -> Điền Mật khẩu rút tiền.")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", _target_el)
                    ActionChains(driver).move_to_element(_target_el).pause(random.uniform(0.1, 0.3)).click().perform()
                    _target_el.clear()
                    _target_el.send_keys(_withdrawal_pass)
                    _b_time.sleep(0.3)

                elif any(kw in _hay for kw in ['chi nhánh', 'chi nhanh', 'branch', 'tỉnh thành', 'phòng giao dịch', 'city', 'province']):
                    print(f"[AI Banking] -> Điền Chi nhánh: {_branch_name}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", _target_el)
                    ActionChains(driver).move_to_element(_target_el).pause(random.uniform(0.1, 0.3)).click().perform()
                    _target_el.clear()
                    _target_el.send_keys(_branch_name)
                    _b_time.sleep(0.3)
            except Exception:
                continue

        _dropdown_xpath = (
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'chọn ngân hàng') or "
            "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'select bank') or "
            "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'choose bank') or "
            "contains(@class, 'select') or contains(@class, 'dropdown') or contains(@class, 'el-select')]"
        )
        _dropdown_triggers = driver.find_elements(_B_By.XPATH, _dropdown_xpath)
        
        for _drop in _dropdown_triggers:
            try:
                if _drop.is_displayed():
                    _drop_text = _drop.text.lower()
                    if any(kw in _drop_text for kw in ['ngân hàng', 'bank', 'chọn', 'select', 'choose']) or len(_drop_text) < 40:
                        print(f"[AI Banking] Đang mở danh sách chọn ngân hàng...")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", _drop)
                        _b_time.sleep(0.3)
                        
    # ==============================================================================
    # LUỒNG MẬT KHẨU RÚT TIỀN & LIÊN KẾT NGÂN HÀNG (TÍCH HỢP ACTIONCHAINS NGƯỜI THẬT)
    # ==============================================================================
    try:
        import time as _b_time
        import random as _b_random
        from selenium.webdriver.common.by import By as _B_By
        from selenium.webdriver.common.action_chains import ActionChains

        # Thoát khỏi iframe cũ để quét đúng trang quản lý
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

        _b_time.sleep(_b_random.uniform(1.0, 2.0))
        print("[AI Banking] Đang quét giao diện liên kết ngân hàng & mật khẩu rút tiền...")

        # Quét các ô input thông minh
        _bank_scan_js = """
        return (() => {
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])'));
            const results = [];
            for (let i = 0; i < inputs.length; i++) {
                const el = inputs[i];
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width < 20 || rect.height < 10 || style.display === 'none' || el.disabled) continue;
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
                    context: ctx.toLowerCase().replace(/\\s+/g, ' ').trim()
                });
            }
            return results;
        })();
        """
        _bank_fields = driver.execute_script(_bank_scan_js) or []
        
        _withdrawal_pass = item.get('withdrawal_pass') or pass_val
        _bank_name_target = item.get('bank_name', 'Techcombank')
        _branch_name = item.get('branch', 'Hà Nội')

        for _f in _bank_fields:
            _hay = f"{_f['name']} {_f['placeholder']} {_f['context']}"
            try:
                _target_el = driver.find_element(_B_By.CSS_SELECTOR, f"input[data-ai-bank-idx='{_f['idx']}']")
                if not _target_el.is_displayed():
                    continue
                
                # Điền Mật khẩu rút tiền / PIN
                if any(kw in _hay for kw in ['mật khẩu rút', 'mat khau rut', 'fund password', 'pin', 'mã pin', 'withdrawal password', 'payment password']):
                    print(f"[AI Banking] -> Điền Mật khẩu rút tiền.")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", _target_el)
                    ActionChains(driver).move_to_element(_target_el).pause(random.uniform(0.1, 0.3)).click().perform()
                    _target_el.clear()
                    _target_el.send_keys(_withdrawal_pass)
                    _b_time.sleep(0.3)

                # Điền Chi nhánh ngân hàng
                elif any(kw in _hay for kw in ['chi nhánh', 'chi nhanh', 'branch', 'tỉnh thành', 'phòng giao dịch', 'city', 'province']):
                    print(f"[AI Banking] -> Điền Chi nhánh: {_branch_name}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", _target_el)
                    ActionChains(driver).move_to_element(_target_el).pause(random.uniform(0.1, 0.3)).click().perform()
                    _target_el.clear()
                    _target_el.send_keys(_branch_name)
                    _b_time.sleep(0.3)
            except Exception:
                continue

        # Xử lý Custom Dropdown chọn Ngân hàng (Dùng ActionChains + Fallback JS click)
        _dropdown_xpath = (
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'chọn ngân hàng') or "
            "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'select bank') or "
            "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'choose bank') or "
            "contains(@class, 'select') or contains(@class, 'dropdown') or contains(@class, 'el-select')]"
        )
        _dropdown_triggers = driver.find_elements(_B_By.XPATH, _dropdown_xpath)
        
        for _drop in _dropdown_triggers:
            try:
                if _drop.is_displayed():
                    _drop_text = _drop.text.lower()
                    if any(kw in _drop_text for kw in ['ngân hàng', 'bank', 'chọn', 'select', 'choose']) or len(_drop_text) < 40:
                        print(f"[AI Banking] Đang mở danh sách chọn ngân hàng...")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", _drop)
                        _b_time.sleep(0.3)
                        
                        # Thử click bằng ActionChains trước, nếu bị che mới dùng JS click
                        try:
                            ActionChains(driver).move_to_element(_drop).pause(random.uniform(0.2, 0.4)).click().perform()
                        except Exception:
                            driver.execute_script("arguments[0].click();", _drop)
                        
                        _b_time.sleep(0.8) # Chờ khung option render xong trên DOM
                        
                        # Quét và chọn tên ngân hàng mục tiêu với cơ chế ActionChains tương tự
                        _bank_options = driver.find_elements(_B_By.XPATH, f"//*[contains(text(), '{_bank_name_target}')]")
                        for _opt in _bank_options:
                            if _opt.is_displayed():
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", _opt)
                                _b_time.sleep(0.2)
                                try:
                                    ActionChains(driver).move_to_element(_opt).pause(random.uniform(0.1, 0.3)).click().perform()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", _opt)
                                print(f"[AI Banking] -> Đã chọn thành công ngân hàng: {_bank_name_target}")
                                break
                        break
            except Exception:
                continue

        print("[AI Banking] Hoàn tất luồng liên kết ngân hàng và mật khẩu rút tiền.")
    except Exception as _bank_exc:
        print(f"[AI Banking] Lưu ý luồng ngân hàng: {type(_bank_exc).__name__}: {_bank_exc}")
    # ==============================================================================
