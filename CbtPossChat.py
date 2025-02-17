import logging
import sqlite3
import nltk
nltk.download('vader_lexicon')
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import random

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
START_CONVERSATION, LISTENING, FEEDBACK = range(3)

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Database functions
def create_database(db_name='cbt_chatbot.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT,
            sentiment_score REAL,
            selected_techniques TEXT,
            feedback TEXT
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Database and tables created successfully.")

# CBT techniques
def suggest_cbt_techniques():
    techniques = {
        "negative": "Cognitive Restructuring: Challenge and reframe negative thoughts.",
        "anxious": "Mindfulness Meditation: Focus on the present moment to reduce anxiety.",
        "anxiety": "Mindfulness Meditation: Focus on the present moment to reduce anxiety.",
        "motivation": "Behavioral Activation: Engage in activities that bring you joy.",
        "stressed": "Deep Breathing Exercises: Practice controlled breathing to alleviate stress.",
        "stress": "Deep Breathing Exercises: Practice controlled breathing to alleviate stress.",
        "self-criticism": "Self-Compassion: Treat yourself with kindness and understanding.",
        "fear": "Exposure Therapy: Gradually face fears in a controlled environment.",
        "decision": "Pros and Cons List: Weigh options to make informed decisions."
    }
    return techniques

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['conversation'] = []
    await update.message.reply_text(
        "Hello! I'm Vza. How are you feeling today?"
    )
    return LISTENING

async def listening(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    context.user_data.setdefault('conversation', []).append(user_input)

    # Decide whether to provide an acknowledgment or ask a prompting question
    if random.random() < 0.3:  # 30% chance to ask a question
        prompts = [
            "Can you tell me more about that?",
            "How does that make you feel?",
            "What else is on your mind?",
            "Why do you think that is?",
            "How long have you felt this way?",
            "What do you think could help?",
            "What's been bothering you the most?",
            "How has this affected you?"
        ]
        prompt = random.choice(prompts)
        await update.message.reply_text(prompt)
    else:
        # Provide minimal acknowledgment
        acknowledgments = [
            "I see.",
            "Go on.",
            "Understood.",
            "I'm here for you.",
            "I understand.",
            "Hmm.",
            "Right.",
            "Okay."
        ]
        acknowledgment = random.choice(acknowledgments)
        await update.message.reply_text(acknowledgment)

    return LISTENING

async def suggest_techniques(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Use the conversation so far to suggest techniques
    conversation = context.user_data.get('conversation', [])
    combined_input = ' '.join(conversation)

    # Analyze sentiment
    sentiment = sia.polarity_scores(combined_input)
    context.user_data['sentiment_score'] = sentiment['compound']

    # Extract keywords
    tokens = word_tokenize(combined_input.lower())
    keywords = set(tokens)
    techniques = suggest_cbt_techniques()

    # Find matching techniques
    matched_techniques = []
    for keyword, technique in techniques.items():
        if keyword.lower() in keywords:
            matched_techniques.append(technique)

    if matched_techniques:
        await update.message.reply_text(
            "Based on what you've shared, here are some techniques that might help:\n" +
            "\n".join(f"- {t}" for t in matched_techniques)
        )
        context.user_data['selected_techniques'] = '; '.join(matched_techniques)
    else:
        await update.message.reply_text(
            "I'm here to support you. Sometimes, engaging in self-care activities like taking a walk or talking to a friend can help."
        )
        context.user_data['selected_techniques'] = 'General Support Provided'

    # Ask for feedback
    await update.message.reply_text("Did you find this helpful? (yes/no)")
    return FEEDBACK

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_feedback = update.message.text.strip().lower()
    if user_feedback in ['yes', 'no']:
        context.user_data['feedback'] = user_feedback
        # Save to database
        save_responses_to_db(update.effective_user.id, context.user_data)

        await update.message.reply_text(
            "Thank you for your feedback. Feel free to share anything else on your mind.\n"
            "If you'd like more suggestions or strategies at any time, just type '/advice'."
        )

        # Reset the conversation data
        context.user_data['conversation'] = []

        return LISTENING
    else:
        await update.message.reply_text("Please answer with 'yes' or 'no'.")
        return FEEDBACK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Conversation ended. Take care!",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def save_responses_to_db(user_id, data, db_name='cbt_chatbot.db'):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO user_responses (
                user_id,
                user_input,
                sentiment_score,
                selected_techniques,
                feedback
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            ' '.join(data.get('conversation', [])),
            data.get('sentiment_score', 0.0),
            data.get('selected_techniques', ''),
            data.get('feedback', '')
        ))

        conn.commit()
        conn.close()
        logger.info(f"User {user_id} responses saved to database.")
    except Exception as e:
        logger.error("Failed to save responses to database.", exc_info=True)

def main():
    # Create the database
    create_database()

    # Telegram Bot Token
    TOKEN = 'telegram bot token'  # Replace with your actual token

    # Build the application
    application = ApplicationBuilder().token(TOKEN).build()

    # Define conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LISTENING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, listening),
                CommandHandler('advice', suggest_techniques),
            ],
            FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback),
                CommandHandler('advice', suggest_techniques),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
