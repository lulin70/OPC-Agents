from flask import Flask, render_template, request, redirect, url_for, jsonify
from memory_classification_engine import MemoryClassificationEngine

app = Flask(__name__)

# Initialize engine
engine = MemoryClassificationEngine()

@app.route('/')
def index():
    """Home page."""
    stats = engine.get_stats()
    return render_template('index.html', stats=stats)

@app.route('/memories')
def memories():
    """List all memories."""
    query = request.args.get('query', '')
    limit = int(request.args.get('limit', 20))
    memories = engine.retrieve_memories(query, limit)
    return render_template('memories.html', memories=memories, query=query, limit=limit)

@app.route('/memory/<memory_id>')
def memory_detail(memory_id):
    """Memory detail page."""
    result = engine.manage_memory('view', memory_id)
    if not result['success']:
        return redirect(url_for('memories'))
    memory = result['memory']
    return render_template('memory_detail.html', memory=memory)

@app.route('/memory/<memory_id>/edit', methods=['GET', 'POST'])
def edit_memory(memory_id):
    """Edit memory page."""
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            result = engine.manage_memory('edit', memory_id, {'content': content})
            if result['success']:
                return redirect(url_for('memory_detail', memory_id=memory_id))
    
    result = engine.manage_memory('view', memory_id)
    if not result['success']:
        return redirect(url_for('memories'))
    memory = result['memory']
    return render_template('edit_memory.html', memory=memory)

@app.route('/memory/<memory_id>/delete')
def delete_memory(memory_id):
    """Delete memory."""
    engine.manage_memory('delete', memory_id)
    return redirect(url_for('memories'))

@app.route('/process', methods=['POST'])
def process_message():
    """Process a message."""
    message = request.form.get('message')
    if message:
        result = engine.process_message(message)
        return redirect(url_for('memories'))
    return redirect(url_for('index'))

@app.route('/api/memories')
def api_memories():
    """API endpoint for memories."""
    query = request.args.get('query', '')
    limit = int(request.args.get('limit', 20))
    memories = engine.retrieve_memories(query, limit)
    return jsonify(memories)

@app.route('/api/process', methods=['POST'])
def api_process():
    """API endpoint for processing messages."""
    data = request.get_json()
    message = data.get('message')
    if message:
        result = engine.process_message(message)
        return jsonify(result)
    return jsonify({'error': 'No message provided'})

if __name__ == '__main__':
    app.run(debug=True)
