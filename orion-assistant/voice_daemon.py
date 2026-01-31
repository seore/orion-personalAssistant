import sys
import json
import time
import threading
import speech_recognition as sr
from orion.utils import get_cloud_command
from orion.ui_cli import dispatch_command
from orion.voice import mac_say
from orion import core

# Configuration
WAKE_WORDS = ["hey titan", "titan"]
CONVERSATION_TIMEOUT = 30  # seconds of silence before requiring wake word again
LISTEN_TIMEOUT = 5  # seconds to wait for speech
PHRASE_TIME_LIMIT = 10  # max seconds per phrase

# State
conversation_active = False
last_interaction_time = 0

def send_status(state):
    """Send status update to Electron"""
    msg = {"type": "status", "state": state}
    print(json.dumps(msg), flush=True)

def send_reply(text):
    """Send reply to Electron"""
    msg = {"type": "reply", "text": text}
    print(json.dumps(msg), flush=True)

def send_transcript(text):
    """Send transcript to Electron"""
    msg = {"type": "transcript", "text": text}
    print(json.dumps(msg), flush=True)

def log(message):
    """Log to stderr (won't interfere with JSON stdout)"""
    print(message, file=sys.stderr, flush=True)

def listen_for_speech(timeout=LISTEN_TIMEOUT, phrase_limit=PHRASE_TIME_LIMIT):
    """Listen for speech and return recognized text"""
    recognizer = sr.Recognizer()
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            
            try:
                audio = recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit
                )
            except sr.WaitTimeoutError:
                return None
            
            try:
                text = recognizer.recognize_google(audio)
                log(f"You said: {text}")
                return text
            except sr.UnknownValueError:
                log("Couldn't understand that")
                return None
            except sr.RequestError as e:
                log(f"Speech recognition error: {e}")
                return None
    except Exception as e:
        log(f"Microphone error: {e}")
        return None

def contains_wake_word(text):
    """Check if text contains any wake word"""
    text_lower = text.lower().strip()
    for wake_word in WAKE_WORDS:
        if wake_word in text_lower:
            return True
    return False

def remove_wake_word(text):
    """Remove wake word from text"""
    text_lower = text.lower().strip()
    for wake_word in WAKE_WORDS:
        if text_lower.startswith(wake_word):
            # Remove wake word and any following comma or punctuation
            remaining = text[len(wake_word):].strip()
            if remaining.startswith(','):
                remaining = remaining[1:].strip()
            return remaining if remaining else text
    return text

def is_conversation_active():
    """Check if we're still in active conversation"""
    global conversation_active, last_interaction_time
    
    if not conversation_active:
        return False
    
    # Check if conversation has timed out
    elapsed = time.time() - last_interaction_time
    if elapsed > CONVERSATION_TIMEOUT:
        log(f"Conversation timeout ({elapsed:.1f}s)")
        conversation_active = False
        return False
    
    return True

def update_interaction_time():
    """Update the last interaction timestamp"""
    global last_interaction_time
    last_interaction_time = time.time()

def activate_conversation():
    """Activate conversation mode"""
    global conversation_active
    conversation_active = True
    update_interaction_time()
    log("Conversation mode activated")

def deactivate_conversation():
    """Deactivate conversation mode"""
    global conversation_active
    conversation_active = False
    log("Conversation mode deactivated")

def process_command(text, data):
    """Process a command and return the reply"""
    try:
        # Get command from Claude
        cmd = get_cloud_command(text)
        
        # Execute command
        reply = dispatch_command(data, cmd)
        
        return reply
    except Exception as e:
        log(f"Error processing command: {e}")
        return "I encountered an error processing that request."

def main():
    """Main daemon loop"""
    log("🎙️  Orion voice daemon starting...")
    log(f"Wake words: {', '.join(WAKE_WORDS)}")
    log(f"Conversation timeout: {CONVERSATION_TIMEOUT}s")
    
    # Load data
    data = core.load_data()
    
    send_status("idle")
    
    while True:
        try:
            # Check if we're in active conversation
            in_conversation = is_conversation_active()
            
            if in_conversation:
                # In conversation - listen without requiring wake word
                log("Listening for follow-up (conversation active)...")
                send_status("listening")
                
                text = listen_for_speech(timeout=8, phrase_limit=15)
                
                if text:
                    send_transcript(text)
                    update_interaction_time()
                    
                    # Process the command
                    send_status("processing")
                    reply = process_command(text, data)
                    
                    # Send reply
                    send_reply(reply)
                    send_status("speaking")
                    
                    # Speak the reply
                    mac_say(reply)
                    
                    # Wait a bit after speaking, then go back to listening
                    time.sleep(1)
                    send_status("listening")
                else:
                    # No speech detected - stay in conversation mode but idle
                    send_status("idle")
                    time.sleep(0.5)
            else:
                # Not in conversation - wait for wake word
                log("Waiting for wake word...")
                send_status("idle")
                
                text = listen_for_speech(timeout=3, phrase_limit=8)
                
                if text and contains_wake_word(text):
                    log("Wake word detected!")
                    send_transcript(text)
                    
                    # Activate conversation mode
                    activate_conversation()
                    
                    # Remove wake word and process command
                    command = remove_wake_word(text)
                    
                    if command and len(command.split()) > 1:
                        # There's a command after the wake word
                        send_status("processing")
                        reply = process_command(command, data)
                        
                        send_reply(reply)
                        send_status("speaking")
                        mac_say(reply)
                        
                        # Keep listening after response
                        time.sleep(1)
                        send_status("listening")
                    else:
                        # Just the wake word, acknowledge and wait for command
                        send_status("listening")
                        mac_say("Yes?")
                        time.sleep(0.5)
                else:
                    # No wake word, keep waiting
                    time.sleep(0.5)
        
        except KeyboardInterrupt:
            log("Shutting down...")
            send_status("idle")
            break
        except Exception as e:
            log(f"Error in main loop: {e}")
            send_status("idle")
            time.sleep(1)

if __name__ == "__main__":
    main()