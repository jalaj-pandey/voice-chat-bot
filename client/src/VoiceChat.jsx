import React, {
  useState,
  useRef,
  forwardRef,
  useImperativeHandle,
} from "react";
import axios from "axios";
import "./styles/VoiceChat.css";

const VoiceChat = forwardRef(({ selectedHotel, onVoiceMessage, style, className }, ref) => {
  const [listening, setListening] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useImperativeHandle(ref, () => ({
    toggleRecording: () => {
      listening ? stopRecording() : startRecording();
    },
  }));

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        const base64Audio = await blobToBase64(audioBlob);

        const res = await axios.post("http://127.0.0.1:8000/voice", {
          audio: base64Audio,
          hotel_name: selectedHotel,
        });

        const botReply = res.data.response;
        const userMessage = res.data.transcript;

        if (onVoiceMessage) {
          onVoiceMessage(userMessage, null);
        }

        setTimeout(() => {
          if (onVoiceMessage) {
            onVoiceMessage(null, botReply);
          }
          speak(botReply);
        },10);
      };

      mediaRecorderRef.current.start();
      setListening(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && listening) {
      mediaRecorderRef.current.stop();
      setListening(false);
    }
  };

  const blobToBase64 = (blob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64Data = reader.result.split(",")[1];
        resolve(base64Data);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  const speak = (text) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div className={`voice-wrapper ${className || ''}`} style={style}>
      <div className="voice-controls">
        <button
          onClick={listening ? stopRecording : startRecording}
          className={`voice-button ${listening ? "listening" : ""}`}
        >
          {listening ? "🛑 Stop Recording" : "🎙️ Start Voice Chat"}
        </button>
      </div>
    </div>
  );
});

export default VoiceChat;