import streamlit as st
import sqlite3
from datetime import datetime
import os

# Create image directory if it doesn't exist
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS entries 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, content TEXT, tags TEXT, 
                  date_added TEXT, image_path TEXT, rating INTEGER DEFAULT 0)''')
    
    # Ensure columns exist for older databases
    columns = [column[1] for column in c.execute("PRAGMA table_info(entries)")]
    if "image_path" not in columns:
        c.execute("ALTER TABLE entries ADD COLUMN image_path TEXT")
    if "rating" not in columns:
        c.execute("ALTER TABLE entries ADD COLUMN rating INTEGER DEFAULT 0")
        
    conn.commit()
    conn.close()

def add_entry(title, content, tags, image_path=None):
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO entries (title, content, tags, date_added, image_path, rating) VALUES (?, ?, ?, ?, ?, 0)", 
              (title, content, tags, date, image_path))
    conn.commit()
    conn.close()

def update_entry(id, title, content, tags, image_path=None):
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    if image_path:
        c.execute("UPDATE entries SET title=?, content=?, tags=?, image_path=? WHERE id=?", 
                  (title, content, tags, image_path, id))
    else:
        c.execute("UPDATE entries SET title=?, content=?, tags=? WHERE id=?", 
                  (title, content, tags, id))
    conn.commit()
    conn.close()

def delete_entry(id):
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    # Optional: Logic to delete the physical image file could go here
    c.execute("DELETE FROM entries WHERE id=?", (id,))
    conn.commit()
    conn.close()

def update_vote(id, current_rating, delta):
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    c.execute("UPDATE entries SET rating=? WHERE id=?", (current_rating + delta, id))
    conn.commit()
    conn.close()

def get_entries(search_term=""):
    conn = sqlite3.connect('knowledge_base.db')
    c = conn.cursor()
    if search_term:
        query = "SELECT * FROM entries WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY rating DESC"
        c.execute(query, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
    else:
        c.execute("SELECT * FROM entries ORDER BY rating DESC, id DESC")
    data = c.fetchall()
    conn.close()
    return data

# --- STREAMLIT UI ---
st.set_page_config(page_title="Local KMS", layout="wide")
init_db()

# Session state to track if we are currently editing a note
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None

st.title("🧠 Local Knowledge Management")

menu = ["Search & View", "Add New Entry"]
choice = st.sidebar.selectbox("Navigation", menu)

# --- ADD NEW ENTRY ---
if choice == "Add New Entry":
    st.subheader("Create a New Note")
    with st.form("entry_form", clear_on_submit=True):
        title = st.text_input("Title")
        tags = st.text_input("Tags (comma separated)")
        content = st.text_area("Content (Markdown supported)", height=300)
        uploaded_file = st.file_uploader("Upload an Image (Optional)", type=["jpg", "jpeg", "png"])
        submit = st.form_submit_button("Save to SQLite")
        
        if submit and title:
            image_path = None
            if uploaded_file is not None:
                image_path = os.path.join("uploads", uploaded_file.name)
                with open(image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            add_entry(title, content, tags, image_path)
            st.success(f"Saved: {title}")

# --- SEARCH, VIEW, EDIT, DELETE ---
elif choice == "Search & View":
    # If in EDIT MODE
    if st.session_state.editing_id:
        st.subheader("🛠️ Edit Note")
        conn = sqlite3.connect('knowledge_base.db')
        curr = conn.cursor()
        curr.execute("SELECT * FROM entries WHERE id=?", (st.session_state.editing_id,))
        note = curr.fetchone()
        conn.close()

        with st.form("edit_form"):
            new_title = st.text_input("Title", value=note[1])
            new_tags = st.text_input("Tags", value=note[3])
            new_content = st.text_area("Content", value=note[2], height=300)
            new_file = st.file_uploader("Replace Image (Optional)", type=["jpg", "jpeg", "png"])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Update Note"):
                    new_img_path = note[5]
                    if new_file:
                        new_img_path = os.path.join("uploads", new_file.name)
                        with open(new_img_path, "wb") as f:
                            f.write(new_file.getbuffer())
                    update_entry(note[0], new_title, new_content, new_tags, new_img_path)
                    st.session_state.editing_id = None
                    st.rerun()
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_id = None
                    st.rerun()
    
    # VIEW MODE
    else:
        search_query = st.text_input("Search your brain...", placeholder="Search titles, content, or tags")
        entries = get_entries(search_query)
        
        for entry in entries:
            # entry indexes: 0:id, 1:title, 2:content, 3:tags, 4:date, 5:img, 6:rating
            score = entry[6] if len(entry) > 6 else 0
            
            with st.expander(f"[{score}] {entry[1]} — ({entry[4]})"):
                st.caption(f"Tags: {entry[3]}")
                st.markdown(entry[2])
                
                # Display Image
                image_path = entry[5]
                if image_path and os.path.exists(image_path):
                    st.image(image_path, use_container_width=True)
                
                # Action Buttons
                c1, c2, c3, c4, c_space = st.columns([0.6, 0.6, 0.8, 0.8, 4])
                with c1:
                    if st.button("👍", key=f"up_{entry[0]}"):
                        update_vote(entry[0], score, 1)
                        st.rerun()
                with c2:
                    if st.button("👎", key=f"down_{entry[0]}"):
                        update_vote(entry[0], score, -1)
                        st.rerun()
                with c3:
                    if st.button("Edit", key=f"edit_{entry[0]}"):
                        st.session_state.editing_id = entry[0]
                        st.rerun()
                with c4:
                    if st.button("Delete", key=f"del_{entry[0]}", help="Permanent Delete"):
                        delete_entry(entry[0])
                        st.rerun()