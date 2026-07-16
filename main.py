import os
import asyncio
import time
import base64
from io import BytesIO
from PIL import Image
import imagehash
import flet as ft


# Global control flags for background scanning
scan_running = False
should_cancel = False

async def main(page: ft.Page):
    def safe_update(control):
        try:
            control.update()
        except Exception:
            pass

    # Session storage setup
    sp = ft.SharedPreferences()
    page.services.append(sp)

    # Load stored settings at startup
    stored_folder = await sp.get("folder_path") or ""
    stored_threshold = await sp.get("threshold")
    stored_groups_per_page = await sp.get("groups_per_page")
    stored_min_size = await sp.get("min_size_kb")
    
    # Defaults
    if stored_threshold is None:
        stored_threshold = 10
    if stored_groups_per_page is None:
        stored_groups_per_page = 20
    if stored_min_size is None:
        stored_min_size = "1"

    # App window configurations
    page.title = "SpyPhotoClean v1.1.1 - Ανίχνευση Όμοιων Φωτογραφιών"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1200
    page.window.height = 850
    page.window.min_width = 800
    page.window.min_height = 600
    page.padding = 0
    page.bgcolor = ft.Colors.BLACK

    # Session pagination state
    all_groups = []
    current_page = 1
    groups_per_page = int(stored_groups_per_page)

    # File picker setup
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def select_folder(e):
        path = await file_picker.get_directory_path()
        if path:
            folder_input.value = path
            folder_input.update()
            await sp.set("folder_path", path)

    # Helper function to open paths in Windows Explorer
    def open_path(path):
        if path and os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as ex:
                page.show_dialog(ft.SnackBar(
                    content=ft.Text(f"Σφάλμα κατά το άνοιγμα: {ex}", color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.RED_800
                ))

    # Helper function to generate image thumbnail as bytes
    def get_thumbnail_bytes(path, max_size=(250, 250)):
        try:
            with Image.open(path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.thumbnail(max_size)
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=75)
                return buffered.getvalue()
        except Exception as e:
            print(f"Σφάλμα thumbnail για {path}: {e}")
            return None

    # Card hover animation
    def card_hover(e):
        if e.data == "true":
            e.control.border = ft.Border.all(2, ft.Colors.BLUE_400)
            e.control.shadow = ft.BoxShadow(
                spread_radius=1,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.35, ft.Colors.BLUE_400),
                offset=ft.Offset(0, 4)
            )
        else:
            e.control.border = ft.Border.all(1, ft.Colors.GREY_800)
            e.control.shadow = None
        e.control.update()

    # Make an individual image card UI
    def make_image_card(img_data, on_delete_click):
        path = img_data["path"]
        filename = os.path.basename(path)
        file_size_mb = img_data["size"] / (1024 * 1024)
        dims_str = f"{img_data['dims'][0]}x{img_data['dims'][1]}"
        
        thumbnail_data = get_thumbnail_bytes(path)
        
        if thumbnail_data:
            b64_str = base64.b64encode(thumbnail_data).decode('utf-8')
            img_control = ft.Image(
                src=b64_str,
                width=240,
                height=150,
                fit=ft.BoxFit.COVER,
                border_radius=ft.BorderRadius.only(top_left=8, top_right=8)
            )
        else:
            img_control = ft.Container(
                content=ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, size=40, color=ft.Colors.RED_400),
                width=240,
                height=150,
                bgcolor=ft.Colors.GREY_900,
                alignment=ft.Alignment.CENTER,
                border_radius=ft.BorderRadius.only(top_left=8, top_right=8)
            )

        parent_dir = os.path.basename(os.path.dirname(path))
        
        card_container = ft.Container(
            width=240,
            height=320,
            bgcolor='#0c0c0e',
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            alignment=ft.Alignment.TOP_CENTER,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_hover=card_hover,
            tooltip=path,
        )

        card_container.content = ft.Column(
            spacing=0,
            controls=[
                img_control,
                ft.Container(
                    padding=10,
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Text(
                                filename, 
                                weight=ft.FontWeight.BOLD, 
                                size=13, 
                                max_lines=1, 
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=filename
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.SD_CARD_OUTLINED, size=12, color=ft.Colors.GREY_400),
                                    ft.Text(f"{file_size_mb:.2f} MB", size=11, color=ft.Colors.GREY_400),
                                ]
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.ASPECT_RATIO, size=12, color=ft.Colors.GREY_400),
                                    ft.Text(dims_str, size=11, color=ft.Colors.GREY_400),
                                ]
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, size=12, color=ft.Colors.GREY_400),
                                    ft.Text(parent_dir, size=11, color=ft.Colors.GREY_400, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=path),
                                ]
                            ),
                            ft.Container(height=2),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.REMOVE_RED_EYE_OUTLINED,
                                        icon_color=ft.Colors.BLUE_400,
                                        icon_size=18,
                                        tooltip="Άνοιγμα εικόνας",
                                        on_click=lambda _: open_path(path)
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_FOREVER_OUTLINED,
                                        icon_color=ft.Colors.RED_400,
                                        icon_size=18,
                                        tooltip="Διαγραφή αρχείου",
                                        on_click=lambda _: on_delete_click(path, card_container)
                                    )
                                ]
                            )
                        ]
                    )
                )
            ]
        )
        return card_container

    # Create UI for a group of similar photos
    def create_group_ui(group_idx, group):
        cards_wrap = ft.Row(
            wrap=True,
            spacing=12,
            run_spacing=12,
            alignment=ft.MainAxisAlignment.START,
        )
        
        group_container = ft.Container(
            bgcolor=ft.Colors.GREY_900,
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            padding=15,
        )
        
        def delete_image_from_group(path, card_control):
            def confirm_delete(e):
                try:
                    os.remove(path)
                    
                    # Remove from the local group list in memory
                    for img in list(group):
                        if img["path"] == path:
                            group.remove(img)
                            break
                    
                    # If the group is left with 1 or 0 cards, remove the whole group from all_groups
                    if len(group) <= 1:
                        if group in all_groups:
                            all_groups.remove(group)
                    
                    page.pop_dialog()
                    page.show_dialog(ft.SnackBar(
                        content=ft.Text(f"Διαγράφηκε επιτυχώς: {os.path.basename(path)}", color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.GREEN_800
                    ))
                    
                    # Refresh the current page to reflect deletion
                    render_current_page()
                    
                except Exception as ex:
                    page.pop_dialog()
                    page.show_dialog(ft.SnackBar(
                        content=ft.Text(f"Σφάλμα κατά τη διαγραφή: {ex}", color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.RED_800
                    ))
                    
            def cancel_delete(e):
                page.pop_dialog()

            dlg = ft.AlertDialog(
                title=ft.Text("Επιβεβαίωση Διαγραφής"),
                content=ft.Text(f"Θέλετε να διαγράψετε οριστικά αυτό το αρχείο;\n\n{os.path.basename(path)}"),
                actions=[
                    ft.TextButton("Ακύρωση", on_click=cancel_delete),
                    ft.TextButton("Διαγραφή", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            page.show_dialog(dlg)

        for img_data in group:
            card = make_image_card(img_data, delete_image_from_group)
            cards_wrap.controls.append(card)
            
        group_container.content = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.COPY_ALL_ROUNDED, color=ft.Colors.AMBER_400, size=20),
                                ft.Text(f"Ομάδα {group_idx}", weight=ft.FontWeight.BOLD, size=15),
                                ft.Container(
                                    bgcolor=ft.Colors.BLUE_900,
                                    border_radius=12,
                                    padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                                    content=ft.Text(f"{len(group)} αρχεία", size=11, color=ft.Colors.BLUE_200, weight=ft.FontWeight.BOLD)
                                )
                            ]
                        ),
                    ]
                ),
                ft.Divider(color=ft.Colors.GREY_800, height=1),
                cards_wrap
            ]
        )
        return group_container

    # Reset UI to standard state
    def reset_scan_ui():
        global scan_running
        scan_running = False
        progress_bar.visible = False
        scan_button.visible = True
        cancel_button.visible = False
        cancel_button.disabled = False
        folder_input.disabled = False
        folder_btn.disabled = False
        threshold_slider.disabled = False
        min_size_input.disabled = False
        open_folder_btn.disabled = False
        safe_update(progress_bar)
        safe_update(scan_button)
        safe_update(cancel_button)
        safe_update(folder_input)
        safe_update(folder_btn)
        safe_update(threshold_slider)
        safe_update(min_size_input)
        safe_update(open_folder_btn)
        safe_update(status_text)

    # Show empty state in results column
    def show_empty_state(message="Επιλέξτε φάκελο και ξεκινήστε την αναζήτηση."):
        results_column.controls.clear()
        results_column.controls.append(
            ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=60,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Icon(ft.Icons.PHOTO_LIBRARY_OUTLINED, size=70, color=ft.Colors.GREY_700),
                        ft.Text(message, size=15, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500),
                    ]
                )
            )
        )
        safe_update(results_column)

    def render_current_page():
        results_column.controls.clear()
        
        if not all_groups:
            show_empty_state("Δεν βρέθηκαν παρόμοιες εικόνες.")
            pagination_container.visible = False
            safe_update(pagination_container)
            return

        pagination_container.visible = True
        
        # Calculate indexes
        total_groups = len(all_groups)
        total_pages = (total_groups + groups_per_page - 1) // groups_per_page
        
        nonlocal current_page
        if current_page > total_pages:
            current_page = total_pages
        if current_page < 1:
            current_page = 1
            
        start_idx = (current_page - 1) * groups_per_page
        end_idx = min(start_idx + groups_per_page, total_groups)
        
        page_groups = all_groups[start_idx:end_idx]
        
        # Update pagination UI text and buttons
        page_info_text.value = f"Σελίδα {current_page} από {total_pages} (Ομάδες {start_idx + 1}-{end_idx} από {total_groups})"
        prev_page_btn.disabled = (current_page == 1)
        next_page_btn.disabled = (current_page == total_pages)
        
        safe_update(pagination_container)
        
        # Add group UIs
        for idx, group in enumerate(page_groups, start=start_idx + 1):
            results_column.controls.append(create_group_ui(idx, group))
            
        safe_update(results_column)

    # Actual background scanning worker
    async def perform_scan(folder_path, threshold):
        global scan_running, should_cancel
        nonlocal current_page
        try:
            
            extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
            image_files = []
            
            # Determine minimum file size limit in bytes
            try:
                min_size_kb = float(min_size_input.value)
            except ValueError:
                min_size_kb = 1.0
            min_size_bytes = min_size_kb * 1024
            
            # 1. Walk directory
            try:
                last_update = time.time()
                for root, dirs, files in os.walk(folder_path):
                    if should_cancel:
                        break
                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in extensions:
                            fpath = os.path.join(root, fname)
                            try:
                                if os.path.getsize(fpath) >= min_size_bytes:
                                    image_files.append(fpath)
                            except Exception:
                                pass
                            # Update status every 0.1 seconds to avoid UI freezing
                            if time.time() - last_update > 0.1:
                                status_text.value = f"Ανίχνευση αρχείων: βρέθηκαν {len(image_files)} εικόνες..."
                                safe_update(status_text)
                                await asyncio.sleep(0.01)
                                last_update = time.time()
            except Exception as ex:
                status_text.value = f"Σφάλμα κατά την ανάγνωση: {ex}"
                reset_scan_ui()
                return
    
            total_files = len(image_files)
            if total_files == 0:
                status_text.value = "Δεν βρέθηκαν υποστηριζόμενες εικόνες στον φάκελο."
                reset_scan_ui()
                show_empty_state("Δεν βρέθηκαν εικόνες στον επιλεγμένο φάκελο.")
                return
    
            # 2. Process hashes & metadata
            scanned_images = []
            for i, path in enumerate(image_files):
                if should_cancel:
                    break
                    
                if i % 5 == 0 or i == total_files - 1:
                    progress_bar.value = i / total_files
                    percentage = int((i / total_files) * 100)
                    status_text.value = f"Ανάλυση εικόνων ({percentage}%) - {i+1}/{total_files}: {os.path.basename(path)}"
                    safe_update(progress_bar)
                    safe_update(status_text)
                    await asyncio.sleep(0.01)
                
                try:
                    with Image.open(path) as img:
                        dims = img.size
                        # Convert to RGB to ensure consistent pHash calculation across different formats (BMP, PNG, JPG)
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        h = imagehash.phash(img)
                        size = os.path.getsize(path)
                        scanned_images.append({
                            "path": path,
                            "hash": h,
                            "size": size,
                            "dims": dims
                        })
                except Exception:
                    continue # Skip invalid files
    
            if should_cancel:
                status_text.value = "Η αναζήτηση ακυρώθηκε."
                reset_scan_ui()
                show_empty_state("Η αναζήτηση ακυρώθηκε.")
                return
    
            # 3. Matching
            groups = []
            used = set()
            total_scanned = len(scanned_images)
            for i, img1 in enumerate(scanned_images):
                if should_cancel:
                    break
                
                # Update matching progress every 5 files or on the last file
                if i % 5 == 0 or i == total_scanned - 1:
                    progress_bar.value = i / total_scanned
                    percentage = int((i / total_scanned) * 100)
                    status_text.value = f"Σύγκριση εικόνων ({percentage}%) - Βρέθηκαν {len(groups)} ομάδες..."
                    safe_update(progress_bar)
                    safe_update(status_text)
                    await asyncio.sleep(0.01)
    
                path1 = img1["path"]
                if path1 in used:
                    continue
                group = [img1]
                for j, img2 in enumerate(scanned_images):
                    path2 = img2["path"]
                    if i != j and path2 not in used:
                        # Aspect ratio check (max 35% difference) to prevent grouping highly dissimilar shapes (e.g. widescreen banners vs photos)
                        w1, h1 = img1["dims"]
                        w2, h2 = img2["dims"]
                        ar1 = w1 / h1
                        ar2 = w2 / h2
                        if abs(ar1 - ar2) / max(ar1, ar2) <= 0.35:
                            if img1["hash"] - img2["hash"] <= threshold:
                                group.append(img2)
                                used.add(path2)
                if len(group) > 1:
                    used.add(path1)
                    groups.append(group)
    
            if should_cancel:
                status_text.value = "Η αναζήτηση ακυρώθηκε."
                reset_scan_ui()
                show_empty_state("Η αναζήτηση ακυρώθηκε.")
                return
    
            # 4. Populate results
            all_groups.clear()
            all_groups.extend(groups)
            current_page = 1
            
            if not all_groups:
                status_text.value = f"Ολοκληρώθηκε. Δεν βρέθηκαν παρόμοιες εικόνες (σύνολο: {total_files})."
                show_empty_state("Δεν βρέθηκαν παρόμοιες εικόνες.")
                pagination_container.visible = False
                safe_update(pagination_container)
            else:
                status_text.value = f"Ολοκληρώθηκε! Βρέθηκαν {len(all_groups)} ομάδες με παρόμοιες εικόνες."
                render_current_page()
            
            reset_scan_ui()

        except Exception as ex:
            import traceback
            tb = traceback.format_exc()
            status_text.value = f"Σφάλμα κατά την αναζήτηση: {ex}"
            with open("crash_log.txt", "w", encoding="utf-8") as f:
                f.write(tb)
            reset_scan_ui()
    # Start scan action triggered by button
    def start_scan_action(e):
        global scan_running, should_cancel
        if scan_running:
            return
            
        folder_path = folder_input.value
        if not folder_path or not os.path.exists(folder_path):
            page.show_dialog(ft.SnackBar(
                content=ft.Text("Παρακαλώ επιλέξτε έναν έγκυρο φάκελο!", color=ft.Colors.WHITE),
                bgcolor=ft.Colors.RED_800
            ))
            return

        scan_running = True
        should_cancel = False
        
        scan_button.visible = False
        cancel_button.visible = True
        cancel_button.disabled = False
        progress_bar.visible = True
        progress_bar.value = 0
        status_text.value = "Αναζήτηση αρχείων..."
        
        folder_input.disabled = True
        folder_btn.disabled = True
        open_folder_btn.disabled = True
        threshold_slider.disabled = True
        min_size_input.disabled = True
        results_column.controls.clear()
        
        safe_update(scan_button)
        safe_update(cancel_button)
        safe_update(progress_bar)
        safe_update(status_text)
        safe_update(folder_input)
        safe_update(folder_btn)
        safe_update(open_folder_btn)
        safe_update(threshold_slider)
        safe_update(min_size_input)
        safe_update(results_column)
        
        # Spawn scanner thread using Flet's thread-safe page.run_thread
        page.run_task(perform_scan, folder_path, int(threshold_slider.value))

    # Cancel scan action triggered by button
    def cancel_scan_action(e):
        global should_cancel
        should_cancel = True
        status_text.value = "Ακύρωση αναζήτησης σε εξέλιξη..."
        cancel_button.disabled = True
        safe_update(status_text)
        safe_update(cancel_button)

    # Help dialog
    def show_help(e):
        help_content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            width=520,
            height=420,
            spacing=12,
            controls=[
                ft.Text("Οδηγίες Χρήσης", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                ft.Divider(color=ft.Colors.GREY_800, height=1),
                ft.Text("1. Επιλογή Φακέλου", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Πληκτρολογήστε τη διαδρομή ή πατήστε το εικονίδιο 📁 για να επιλέξετε φάκελο. "
                         "Η αναζήτηση γίνεται αναδρομικά σε όλους τους υποφακέλους.", size=13, color=ft.Colors.GREY_300),
                ft.Text("2. Συντελεστής Ομοιότητας", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("• 0: Μόνο πανομοιότυπα αρχεία\n"
                         "• 1–9: Σχεδόν πανομοιότυπα\n"
                         "• 10–19: Πολύ παρόμοια (Προτεινόμενο)\n"
                         "• 20+: Χαλαρό φιλτράρισμα (πιθανά ψευδή θετικά)", size=13, color=ft.Colors.GREY_300),
                ft.Text("3. Σάρωση & Αποτελέσματα", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Πατήστε «Έναρξη Αναζήτησης». Η εφαρμογή εντοπίζει εικόνες (JPG, PNG, GIF, BMP, TIFF, WebP), "
                         "υπολογίζει perceptual hash (pHash) και ομαδοποιεί τις παρόμοιες.", size=13, color=ft.Colors.GREY_300),
                ft.Text("4. Διαχείριση Φωτογραφιών", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("• 👁️ Προβολή: Ανοίγει τη φωτογραφία σε πλήρη ανάλυση\n"
                         "• 🗑️ Διαγραφή: Διαγράφει οριστικά το αρχείο (με επιβεβαίωση)", size=13, color=ft.Colors.GREY_300),
                ft.Container(
                    bgcolor=ft.Colors.RED_900,
                    border_radius=6,
                    padding=10,
                    content=ft.Text("⚠️ Προσοχή: Η διαγραφή είναι μόνιμη — τα αρχεία δεν πηγαίνουν στον Κάδο Ανακύκλωσης.",
                                    size=12, color=ft.Colors.RED_200, weight=ft.FontWeight.BOLD)
                ),
                ft.Divider(color=ft.Colors.GREY_800, height=1),
                ft.Text("Υποστηριζόμενοι τύποι: JPG, JPEG, PNG, GIF, BMP, TIFF, WebP", size=12, color=ft.Colors.GREY_500, italic=True),
            ]
        )
        dlg = ft.AlertDialog(
            title=ft.Row(controls=[
                ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, color=ft.Colors.BLUE_400, size=24),
                ft.Text("SpyPhotoClean — Βοήθεια", weight=ft.FontWeight.BOLD, size=16)
            ]),
            content=help_content,
            actions=[ft.TextButton("Κλείσιμο", on_click=lambda _: page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    # UI controls creation
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.PHOTO_LIBRARY_ROUNDED, size=34, color=ft.Colors.BLUE_400),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text("SpyPhotoClean v1.1.1", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Εντοπισμός και διαγραφή οπτικά παρόμοιων φωτογραφιών με χρήση phash", size=12, color=ft.Colors.GREY_400)
                    ]
                ),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                    icon_color=ft.Colors.GREY_400,
                    icon_size=22,
                    tooltip="Βοήθεια",
                    on_click=show_help,
                )
            ]
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=15),
        bgcolor='#0c0c0e',
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.GREY_900)
    )

    folder_input = ft.TextField(
        label="Φάκελος για αναζήτηση",
        value=stored_folder,
        expand=True,
        border_color=ft.Colors.GREY_800,
        focused_border_color=ft.Colors.BLUE_400,
        text_style=ft.TextStyle(color=ft.Colors.WHITE),
        label_style=ft.TextStyle(color=ft.Colors.GREY_400),
        cursor_color=ft.Colors.BLUE_400,
    )
    
    async def folder_input_changed(e):
        await sp.set("folder_path", folder_input.value)
    folder_input.on_change = folder_input_changed
    
    folder_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        icon_color=ft.Colors.BLUE_400,
        tooltip="Επιλογή φακέλου",
        on_click=select_folder,
        icon_size=24
    )

    open_folder_btn = ft.IconButton(
        icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
        icon_color=ft.Colors.BLUE_400,
        tooltip="Άνοιγμα φακέλου στον Windows Explorer",
        on_click=lambda _: open_path(folder_input.value),
        icon_size=24
    )

    threshold_slider = ft.Slider(
        min=0,
        max=30,
        divisions=30,
        value=float(stored_threshold),
        label="{value}",
        active_color=ft.Colors.BLUE_400,
        inactive_color=ft.Colors.GREY_800,
    )
    
    def get_threshold_desc(val):
        if val == 0:
            return "Μόνο πανομοιότυπες"
        elif val < 10:
            return "Σχεδόν πανομοιότυπες"
        elif val < 20:
            return "Πολύ παρόμοιες (Προτεινόμενο)"
        else:
            return "Παρόμοιες (Πιθανά λανθασμένες θετικά)"
            
    init_desc = get_threshold_desc(int(stored_threshold))
    threshold_info = ft.Text(f"Συντελεστής ομοιότητας: {int(stored_threshold)} ({init_desc})", size=12, color=ft.Colors.GREY_400)
    
    async def slider_changed(e):
        val = int(threshold_slider.value)
        desc = get_threshold_desc(val)
        threshold_info.value = f"Συντελεστής ομοιότητας: {val} ({desc})"
        threshold_info.update()
        await sp.set("threshold", val)
        
    threshold_slider.on_change = slider_changed

    min_size_input = ft.TextField(
        label="Ελάχ. μέγεθος (KB)",
        value=str(stored_min_size),
        width=150,
        border_color=ft.Colors.GREY_800,
        focused_border_color=ft.Colors.BLUE_400,
        text_style=ft.TextStyle(color=ft.Colors.WHITE),
        label_style=ft.TextStyle(color=ft.Colors.GREY_400),
        cursor_color=ft.Colors.BLUE_400,
    )
    
    async def min_size_changed(e):
        await sp.set("min_size_kb", min_size_input.value)
    min_size_input.on_change = min_size_changed

    scan_button = ft.Button(
        content="Έναρξη Αναζήτησης",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            padding=ft.Padding.all(16),
            shape=ft.RoundedRectangleBorder(radius=6)
        ),
        on_click=start_scan_action
    )
    
    cancel_button = ft.Button(
        content="Ακύρωση",
        icon=ft.Icons.CANCEL_ROUNDED,
        visible=False,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.RED_600,
            color=ft.Colors.WHITE,
            padding=ft.Padding.all(16),
            shape=ft.RoundedRectangleBorder(radius=6)
        ),
        on_click=cancel_scan_action
    )

    settings_card = ft.Container(
        bgcolor='#0c0c0e',
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.GREY_900),
        padding=18,
        content=ft.Column(
            spacing=15,
            controls=[
                ft.Row(
                    controls=[
                        folder_input,
                        folder_btn,
                        open_folder_btn
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Row(
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=3,
                            controls=[
                                threshold_info,
                                threshold_slider
                            ]
                        ),
                        ft.Container(width=10),
                        min_size_input,
                        ft.Container(width=10),
                        ft.Row(
                            controls=[
                                scan_button,
                                cancel_button
                            ]
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            ]
        )
    )

    progress_bar = ft.ProgressBar(value=0, visible=False, color=ft.Colors.BLUE_400, bgcolor=ft.Colors.GREY_900)
    status_text = ft.Text(value="", size=12, color=ft.Colors.GREY_400, italic=True)

    progress_area = ft.Column(
        spacing=5,
        controls=[
            progress_bar,
            status_text
        ]
    )

    results_column = ft.Column(
        spacing=18,
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )

    # Pagination controls
    prev_page_btn = ft.IconButton(
        icon=ft.Icons.NAVIGATE_BEFORE,
        icon_color=ft.Colors.BLUE_400,
        disabled=True,
        tooltip="Προηγούμενη σελίδα"
    )
    
    next_page_btn = ft.IconButton(
        icon=ft.Icons.NAVIGATE_NEXT,
        icon_color=ft.Colors.BLUE_400,
        disabled=True,
        tooltip="Επόμενη σελίδα"
    )
    
    page_info_text = ft.Text(
        value="Σελίδα 1 από 1",
        size=13,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD
    )
    
    per_page_dropdown = ft.Dropdown(
        width=100,
        height=40,
        text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
        border_color=ft.Colors.GREY_800,
        focused_border_color=ft.Colors.BLUE_400,
        options=[
            ft.dropdown.Option("10"),
            ft.dropdown.Option("20"),
            ft.dropdown.Option("50"),
            ft.dropdown.Option("100")
        ],
        value=str(stored_groups_per_page)
    )
    
    async def per_page_changed(e):
        nonlocal groups_per_page, current_page
        if per_page_dropdown.value:
            groups_per_page = int(per_page_dropdown.value)
        current_page = 1
        await sp.set("groups_per_page", per_page_dropdown.value)
        render_current_page()
        
    per_page_dropdown.on_change = per_page_changed

    def go_prev_page(e):
        nonlocal current_page
        if current_page > 1:
            current_page -= 1
            render_current_page()
            
    def go_next_page(e):
        nonlocal current_page
        total_pages = (len(all_groups) + groups_per_page - 1) // groups_per_page
        if current_page < total_pages:
            current_page += 1
            render_current_page()
            
    prev_page_btn.on_click = go_prev_page
    next_page_btn.on_click = go_next_page

    pagination_container = ft.Container(
        bgcolor='#0c0c0e',
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.GREY_900),
        padding=ft.Padding(left=12, top=8, right=12, bottom=8),
        visible=False,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=5,
                    controls=[
                        prev_page_btn,
                        page_info_text,
                        next_page_btn
                    ]
                ),
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Ομάδες ανά σελίδα:", size=12, color=ft.Colors.GREY_400),
                        per_page_dropdown
                    ]
                )
            ]
        )
    )

    # Initial UI Setup
    show_empty_state()

    main_container = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.GREY_900, '#0f131c', ft.Colors.BLACK]
        ),
        expand=True,
        padding=18,
        content=ft.Column(
            spacing=12,
            controls=[
                header,
                settings_card,
                progress_area,
                pagination_container,
                ft.Text("Αποτελέσματα", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                results_column
            ],
            expand=True
        )
    )

    page.add(main_container)

    # Close PyInstaller native splash screen if running as compiled bundle
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
