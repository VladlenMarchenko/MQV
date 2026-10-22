import tkinter as tk
from tkinter import messagebox, scrolledtext

from app import (
    build_high_volume_block,
    build_letter,
    classify_queues,
    collect_high_volume,
    load_rules,
    load_signature,
    save_signature,
    split_queues,
)

high_volume_window = None


def show_high_volume_window(items: list[str]):
    global high_volume_window

    if high_volume_window is not None and high_volume_window.winfo_exists():
        high_volume_window.destroy()
        high_volume_window = None

    if not items:
        return

    high_volume_window = tk.Toplevel(root)
    high_volume_window.title('Очереди с большим кол-вом сообщений')
    high_volume_window.geometry('900x320')
    high_volume_window.minsize(640, 220)

    frame = tk.Frame(high_volume_window, padx=14, pady=14)
    frame.pack(fill=tk.BOTH, expand=True)

    title = tk.Label(
        frame,
        text='!!!ОЧЕРЕДИ С БОЛЬШИМ КОЛ-ВОМ СООБЩЕНИЙ!!!',
        fg='#b91c1c',
        font=('Segoe UI', 12, 'bold'),
        anchor='w',
        justify='left',
    )
    title.pack(fill=tk.X, pady=(0, 8))

    text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=10, font=('Consolas', 11))
    text.pack(fill=tk.BOTH, expand=True)
    text.insert(tk.END, build_high_volume_block(items))
    text.config(state=tk.DISABLED)


def generate_letter():
    raw = input_text.get('1.0', tk.END).strip()
    try:
        queues = split_queues(raw)
        rules = load_rules()
        grouped = classify_queues(queues, rules)
        high_volume = collect_high_volume(queues)
        letter = build_letter(grouped, signature_text.get('1.0', tk.END).strip())

        result_text.config(state=tk.NORMAL)
        result_text.delete('1.0', tk.END)
        result_text.insert(tk.END, letter)

        show_high_volume_window(high_volume)

        if grouped['unmatched']:
            warn_var.set('Внимание: часть очередей не сопоставлена правилам NP: ' + ', '.join(grouped['unmatched']))
        else:
            warn_var.set('')
    except Exception as exc:
        messagebox.showerror('Ошибка', str(exc))


def paste_input():
    try:
        text = root.clipboard_get()
    except tk.TclError:
        return
    input_text.insert(tk.INSERT, text)
    input_text.focus_set()


def save_signature_click():
    save_signature(signature_text.get('1.0', tk.END).strip())
    messagebox.showinfo('Подпись', 'Подпись сохранена.')


def copy_result():
    text = result_text.get('1.0', tk.END).strip()
    if not text:
        return
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()


root = tk.Tk()
root.title('Генератор письма по очередям')
root.geometry('1100x860')
root.minsize(900, 720)

container = tk.Frame(root, padx=14, pady=14)
container.pack(fill=tk.BOTH, expand=True)

header = tk.Label(container, text='Вставьте очереди (каждая с новой строки или через , ;) и нажмите кнопку:', anchor='w', justify='left')
header.pack(fill=tk.X)

input_text = scrolledtext.ScrolledText(container, wrap=tk.WORD, height=15, font=('Consolas', 11))
input_text.pack(fill=tk.BOTH, expand=False, pady=(8, 10))

buttons = tk.Frame(container)
buttons.pack(fill=tk.X)

paste_btn = tk.Button(buttons, text='Вставить из буфера', command=paste_input)
paste_btn.pack(side=tk.LEFT)

generate_btn = tk.Button(buttons, text='Сформировать письмо', command=generate_letter)
generate_btn.pack(side=tk.LEFT, padx=(10, 0))

copy_btn = tk.Button(buttons, text='Копировать результат', command=copy_result)
copy_btn.pack(side=tk.LEFT, padx=(10, 0))

warn_var = tk.StringVar(value='')
warn_label = tk.Label(container, textvariable=warn_var, fg='#b45309', anchor='w', justify='left', wraplength=1020)
warn_label.pack(fill=tk.X, pady=(10, 6))

signature_label = tk.Label(container, text='Подпись (добавляется в конец письма):', anchor='w', justify='left')
signature_label.pack(fill=tk.X)

signature_text = scrolledtext.ScrolledText(container, wrap=tk.WORD, height=3, font=('Segoe UI', 11))
signature_text.pack(fill=tk.X, pady=(4, 6))

signature_buttons = tk.Frame(container)
signature_buttons.pack(fill=tk.X, pady=(0, 10))

save_signature_btn = tk.Button(signature_buttons, text='Сохранить подпись', command=save_signature_click)
save_signature_btn.pack(side=tk.LEFT)

saved_signature = load_signature()
if saved_signature:
    signature_text.insert(tk.END, saved_signature)

result_label = tk.Label(container, text='Результат', anchor='w', justify='left', font=('Segoe UI', 12, 'bold'))
result_label.pack(fill=tk.X)

result_text = scrolledtext.ScrolledText(container, wrap=tk.WORD, height=16, font=('Segoe UI', 12))
result_text.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

input_text.bind('<Control-v>', lambda e: (paste_input(), 'break')[1])
input_text.bind('<Control-V>', lambda e: (paste_input(), 'break')[1])
input_text.bind('<Shift-Insert>', lambda e: (paste_input(), 'break')[1])

root.mainloop()
