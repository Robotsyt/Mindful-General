from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import json
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from functools import wraps
import time
from models import db, FeelingCheck, JournalEntry, ChatInteraction, DailyGoal, BreathingSession, JournalPrompt

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mindful.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# Rate limiting decorator
def rate_limit(limit=5, per=60):
    rates = {}
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            now = time.time()
            ip = request.remote_addr
            if ip in rates:
                last_time, count = rates[ip]
                if now - last_time >= per:
                    rates[ip] = (now, 1)
                elif count >= limit:
                    return jsonify({"error": "Rate limit exceeded"}), 429
                else:
                    rates[ip] = (last_time, count + 1)
            else:
                rates[ip] = (now, 1)
            return f(*args, **kwargs)
        return wrapped
    return decorator

def get_gemini_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API key not found in environment variables")
    return ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=api_key)

JOURNAL_PROMPTS = [
    {"text": "What made you smile today?", "category": "gratitude"},
    {"text": "What's a challenge you overcame recently?", "category": "growth"},
    {"text": "Describe a moment that made you feel proud.", "category": "reflection"},
    {"text": "What's something you're looking forward to?", "category": "gratitude"},
    {"text": "How have you grown in the past month?", "category": "growth"},
    {"text": "What's a small thing you're grateful for today?", "category": "gratitude"},
    {"text": "What would make today great?", "category": "reflection"},
    {"text": "What's a lesson you learned recently?", "category": "growth"},
]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/journal/prompts", methods=['GET'])
def get_journal_prompts():
    category = request.args.get('category', None)
    prompts = JournalPrompt.query.filter_by(is_active=True)
    if category:
        prompts = prompts.filter_by(category=category)
    return jsonify([{"id": p.id, "text": p.prompt_text, "category": p.category} for p in prompts.all()])

@app.route('/api/journal', methods=['GET', 'POST', 'PUT'])
def journal_api():
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = 10
        tag_filter = request.args.get('tag', '')
        mood_filter = request.args.get('mood', '')

        query = JournalEntry.query
        if tag_filter:
            query = query.filter(JournalEntry.tags.contains(tag_filter))
        if mood_filter:
            query = query.filter_by(mood=mood_filter)

        entries = query.order_by(JournalEntry.created_at.desc()).paginate(page=page, per_page=per_page)
        
        return jsonify({
            'entries': [{
                'id': entry.id,
                'title': entry.title,
                'content': entry.content,
                'mood': entry.mood,
                'tags': entry.tags,
                'prompt': entry.prompt,
                'favorite': entry.favorite,
                'created_at': entry.created_at.isoformat()
            } for entry in entries.items],
            'total_pages': entries.pages,
            'current_page': entries.page
        })

    elif request.method in ['POST', 'PUT']:
        data = request.json
        if request.method == 'PUT' and 'id' not in data:
            return jsonify({'error': 'Entry ID required for update'}), 400

        try:
            if request.method == 'PUT':
                entry = JournalEntry.query.get(data['id'])
                if not entry:
                    return jsonify({'error': 'Entry not found'}), 404
            else:
                entry = JournalEntry()
                entry.created_at = datetime.utcnow()

            entry.title = data['title']
            entry.content = data['content']
            entry.mood = data['mood']
            entry.tags = data['tags']
            entry.prompt = data.get('prompt', '')
            entry.favorite = data.get('favorite', False)

            if request.method == 'POST':
                db.session.add(entry)
            db.session.commit()

            return jsonify({
                'id': entry.id,
                'message': 'Journal entry saved successfully'
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route('/api/journal/<int:entry_id>', methods=['GET', 'DELETE'])
def journal_entry_api(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    
    if request.method == 'GET':
        return jsonify({
            'id': entry.id,
            'title': entry.title,
            'content': entry.content,
            'mood': entry.mood,
            'tags': entry.tags,
            'prompt': entry.prompt,
            'favorite': entry.favorite,
            'created_at': entry.created_at.isoformat()
        })
    
    elif request.method == 'DELETE':
        try:
            db.session.delete(entry)
            db.session.commit()
            return jsonify({'message': 'Entry deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route("/api/progress", methods=["GET"])
@rate_limit(limit=10, per=60)
def progress_api():
    feelings = FeelingCheck.query.order_by(FeelingCheck.timestamp.desc()).limit(30).all()
    chats = ChatInteraction.query.order_by(ChatInteraction.timestamp.desc()).limit(50).all()
    breathing = BreathingSession.query.order_by(BreathingSession.timestamp.desc()).limit(20).all()
    goals = DailyGoal.query.filter(DailyGoal.date >= date.today()).all()
    
    return jsonify({
        "feelings": [{
            "feeling": f.feeling,
            "note": f.note,
            "timestamp": f.timestamp.isoformat()
        } for f in feelings],
        "interactions": [{
            "message": c.user_message,
            "response": c.bot_response,
            "timestamp": c.timestamp.isoformat()
        } for c in chats],
        "breathing_sessions": [{
            "type": b.exercise_type,
            "duration": b.duration,
            "timestamp": b.timestamp.isoformat()
        } for b in breathing],
        "goals": [{
            "goal": g.goal,
            "completed": g.completed,
            "date": g.date.isoformat()
        } for g in goals]
    })

@app.route("/api/breathing", methods=["POST"])
@rate_limit(limit=10, per=60)
def breathing_api():
    try:
        data = request.get_json()
        session = BreathingSession(
            exercise_type=data['type'],
            duration=data['duration']
        )
        db.session.add(session)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/goals", methods=["POST", "GET"])
@rate_limit(limit=10, per=60)
def goals_api():
    if request.method == "POST":
        try:
            data = request.get_json()
            goal = DailyGoal(
                goal=data['goal'],
                date=date.today()
            )
            db.session.add(goal)
            db.session.commit()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        goals = DailyGoal.query.filter(DailyGoal.date >= date.today()).all()
        return jsonify([{
            "id": g.id,
            "goal": g.goal,
            "completed": g.completed,
            "date": g.date.isoformat()
        } for g in goals])

@app.route('/api/feeling', methods=['POST'])
def feeling_api():
    try:
        data = request.get_json()
        feeling = data.get('feeling')
        
        if not feeling:
            return jsonify({"error": "Feeling is required"}), 400

        # Save feeling check
        feeling_check = FeelingCheck(feeling=feeling)
        db.session.add(feeling_check)
        db.session.commit()

        # Generate response based on feeling
        responses = {
            'Great': "That's wonderful to hear! What's making today so great for you?",
            'Good': "I'm glad you're feeling good! Would you like to share what's going well?",
            'Okay': "Sometimes 'okay' is perfectly fine. Is there anything you'd like to talk about?",
            'Bad': "I'm sorry you're not feeling your best. Would you like to talk about what's troubling you?",
            'Terrible': "I'm here for you during this difficult time. Would you like to share what's making you feel this way?"
        }
        
        response = responses.get(feeling, "Thank you for sharing how you're feeling. Would you like to talk about it?")
        
        return jsonify({
            "response": response,
            "status": "success"
        })

    except Exception as e:
        app.logger.error(f"Error in feeling_api: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/api/generate", methods=["POST"])
def generate_api():
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        content = data.get("contents")
        
        if not content:
            return jsonify({"error": "Message content is required"}), 400

        model = get_gemini_model()
        message = HumanMessage(content=content)
        response = model.invoke([message])

        # Save chat interaction
        chat = ChatInteraction(
            user_message=content,
            bot_response=response.content
        )
        db.session.add(chat)
        db.session.commit()

        return jsonify({
            "response": response.content,
            "status": "success"
        })

    except Exception as e:
        app.logger.error(f"Error in generate_api: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/visualizations/mood-trends', methods=['GET'])
def mood_trends():
    # Get mood data for the last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    mood_data = FeelingCheck.query.filter(FeelingCheck.timestamp >= seven_days_ago).all()
    
    # Process data for visualization
    mood_counts = {}
    dates = []
    for entry in mood_data:
        date_str = entry.timestamp.strftime('%Y-%m-%d')
        if date_str not in dates:
            dates.append(date_str)
        mood_counts[entry.feeling] = mood_counts.get(entry.feeling, 0) + 1
    
    return jsonify({
        'dates': dates,
        'mood_counts': mood_counts
    })

@app.route('/api/visualizations/wellness-stats', methods=['GET'])
def wellness_stats():
    # Get stats for the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get various wellness metrics
    journal_count = JournalEntry.query.filter(JournalEntry.timestamp >= thirty_days_ago).count()
    breathing_sessions = BreathingSession.query.filter(BreathingSession.timestamp >= thirty_days_ago).count()
    completed_goals = DailyGoal.query.filter(
        DailyGoal.date >= thirty_days_ago.date(),
        DailyGoal.completed == True
    ).count()
    total_goals = DailyGoal.query.filter(DailyGoal.date >= thirty_days_ago.date()).count()
    
    return jsonify({
        'journal_entries': journal_count,
        'breathing_sessions': breathing_sessions,
        'completed_goals': completed_goals,
        'total_goals': total_goals,
        'goal_completion_rate': (completed_goals / total_goals * 100) if total_goals > 0 else 0
    })

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=False)  # Set debug=False in production
