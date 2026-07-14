const STORAGE_KEY = "daily-todos";

const todoForm = document.getElementById("todo-form");
const todoInput = document.getElementById("todo-input");
const todoList = document.getElementById("todo-list");
const emptyMessage = document.getElementById("empty-message");

let todos = loadTodos();

function loadTodos() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

function saveTodos() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

function renderTodos() {
  todoList.innerHTML = "";

  todos.forEach((todo) => {
    const item = document.createElement("li");
    item.className = "todo-item";
    item.dataset.id = todo.id;

    const label = document.createElement("label");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = todo.completed;
    checkbox.addEventListener("change", () => toggleTodo(todo.id));

    const text = document.createElement("span");
    text.className = `todo-text${todo.completed ? " completed" : ""}`;
    text.textContent = todo.text;

    label.append(checkbox, text);

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-btn";
    deleteBtn.textContent = "삭제";
    deleteBtn.addEventListener("click", () => deleteTodo(todo.id));

    item.append(label, deleteBtn);
    todoList.appendChild(item);
  });

  emptyMessage.classList.toggle("hidden", todos.length > 0);
}

function addTodo(text) {
  todos.push({
    id: crypto.randomUUID(),
    text,
    completed: false,
  });
  saveTodos();
  renderTodos();
}

function toggleTodo(id) {
  todos = todos.map((todo) =>
    todo.id === id ? { ...todo, completed: !todo.completed } : todo
  );
  saveTodos();
  renderTodos();
}

function deleteTodo(id) {
  todos = todos.filter((todo) => todo.id !== id);
  saveTodos();
  renderTodos();
}

todoForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const text = todoInput.value.trim();
  if (!text) return;

  addTodo(text);
  todoInput.value = "";
  todoInput.focus();
});

renderTodos();
