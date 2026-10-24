import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8008";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000,
});

/**
 * Silent health ping called on app mount to wake up Render free tier container in background.
 */
export const pingBackendHealth = async () => {
  try {
    await apiClient.get("/health", { timeout: 15000 });
  } catch (err) {
    // Silent fail; purely used to wake up the cloud container early
    console.debug("Silent backend wake-up ping:", err?.message);
  }
};

export const predictNews = async (title, text) => {
  try {
    const response = await apiClient.post("/predict", {
      title: title || "",
      text: text || "",
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      if (error.response.status === 422) {
        const detail = error.response.data?.detail;
        if (typeof detail === "string") {
          throw new Error(detail);
        } else if (Array.isArray(detail) && detail.length > 0) {
          throw new Error(detail[0].msg || "Validation error: Please enter valid headline or text.");
        }
        throw new Error("Validation error: Please enter a headline or article text.");
      }
      throw new Error(error.response.data?.detail || "Unable to process prediction request. Please try again later.");
    } else if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
      throw new Error("Prediction request timed out. Please try again.");
    } else if (error.request) {
      throw new Error("Unable to connect to the backend server. Please check if the API server is running on " + API_BASE_URL + ".");
    } else {
      throw new Error("An unexpected error occurred while making the request.");
    }
  }
};

export const verifyNewsV2 = async (title, text, language = "auto", isRetry = false, sourceUrl = "") => {
  try {
    const payload = {
      title: title || "",
      text: text || "",
      language: language || "auto",
    };
    if (sourceUrl) {
      payload.source_url = sourceUrl;
    }
    const response = await apiClient.post("/v2/verify", payload);
    return response.data;
  } catch (error) {
    // Auto-retry once if timeout or connection drop occurred (server was waking up)
    if (!isRetry && (error.code === "ECONNABORTED" || error.message?.includes("timeout") || !error.response)) {
      console.warn("Server cold start or network delay detected. Retrying verification automatically...");
      return await verifyNewsV2(title, text, language, true, sourceUrl);
    }
    if (error.response) {
      if (error.response.status === 422) {
        const detail = error.response.data?.detail;
        if (typeof detail === "string") {
          throw new Error(detail);
        } else if (Array.isArray(detail) && detail.length > 0) {
          throw new Error(detail[0].msg || "Validation error: Please enter valid title or text.");
        }
        throw new Error("Validation error: At least a title or text of sufficient length is required for verification.");
      }
      throw new Error(error.response.data?.detail || "Unable to complete real-time news verification. Please try again.");
    } else if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
      throw new Error("The cloud verification engine was waking up from standby and took longer than expected. The server is now awake — please click Verify again!");
    } else if (error.request) {
      throw new Error("Unable to connect to the backend verification server. The server is waking up from standby — please try again in a moment.");
    } else {
      throw new Error("An unexpected error occurred during verification.");
    }
  }
};

export const extractArticleFromUrl = async (url) => {
  try {
    const response = await apiClient.post("/v2/extract-url", { url });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to extract content from the given URL.");
  }
};

export const auditDocumentText = async (title, content) => {
  try {
    const response = await apiClient.post("/v2/audit-document", {
      title: title || "",
      content: content || "",
    });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to audit document content.");
  }
};

export const auditUploadedFile = async (file) => {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/v2/audit-file", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 90000,
    });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to audit uploaded file.");
  }
};

export const getAnalyticsData = async (domain = "") => {
  try {
    const params = domain ? { domain } : {};
    const response = await apiClient.get("/v2/analytics", { params });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to fetch analytics intelligence data.");
  }
};

export const getRadarFeed = async (category = "", country = "IN", rotate = false) => {
  try {
    const params = {};
    if (category && category !== "All") params.category = category;
    if (country) params.country = country;
    if (rotate) params.rotate = true;
    const response = await apiClient.get("/v2/radar", { params });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to fetch live radar trending feed.");
  }
};

export const auditUploadedImage = async (file) => {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/v2/audit-image", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000,
    });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to audit uploaded image.");
  }
};

export const auditUploadedAudio = async (fileOrBlob, filename = "recording.wav", transcriptHint = "") => {
  try {
    const formData = new FormData();
    formData.append("file", fileOrBlob, filename);
    if (transcriptHint && transcriptHint.trim()) {
      formData.append("transcript_hint", transcriptHint.trim());
    }
    const response = await apiClient.post("/v2/audit-audio", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000,
    });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to audit audio recording.");
  }
};

export const transcribeAudioFast = async (fileOrBlob, filename = "audio.webm") => {
  try {
    const formData = new FormData();
    formData.append("file", fileOrBlob, filename);
    const response = await apiClient.post("/v2/transcribe-audio", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 30000,
    });
    return response.data?.transcription || "";
  } catch (error) {
    console.warn("Fast transcription failed:", error);
    return "";
  }
};

export const fetchAudioSamples = async () => {
  try {
    const response = await apiClient.get("/v2/audio-samples");
    return response.data?.samples || [];
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to fetch preset audio samples.");
  }
};

export const auditAudioPreset = async (sampleId) => {
  try {
    const response = await apiClient.post(`/v2/audit-audio-preset/${sampleId}`);
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to audit preset audio sample.");
  }
};

// =========================================================================
// Feature 3: WhatsApp & Telegram Webhook Chatbot Bridge API
// =========================================================================

export const verifyBotMessage = async (messageText, platform = "whatsapp", isForwarded = false) => {
  try {
    const response = await apiClient.post("/v2/bot/verify", {
      message_text: messageText,
      platform: platform,
      is_forwarded: isForwarded
    });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to verify forwarded message.");
  }
};

export const fetchBotPresets = async () => {
  try {
    const response = await apiClient.get("/v2/bot/presets");
    return response.data || [];
  } catch (error) {
    console.warn("Failed to fetch bot presets:", error);
    return [];
  }
};

export const simulateWebhookCall = async (platform, payload) => {
  try {
    const endpoint = platform === "telegram" ? "/v2/bot/webhook/telegram" : "/v2/bot/webhook/whatsapp";
    const response = await apiClient.post(endpoint, payload);
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to simulate webhook dispatch.");
  }
};

// =========================================================================
// AUTHENTICATION API
// =========================================================================

apiClient.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem("truthlens_auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (e) {
    // ignore
  }
  return config;
});

export const loginUser = async (email, password) => {
  try {
    const response = await apiClient.post("/v2/auth/login", { email, password });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to sign in. Please verify your credentials.");
  }
};

export const signupUser = async ({ name, email, password, role = "Fact-Checker" }) => {
  try {
    const response = await apiClient.post("/v2/auth/signup", { name, email, password, role });
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to create account. Please try again.");
  }
};

export const loginDemoUser = async () => {
  try {
    const response = await apiClient.post("/v2/auth/demo");
    return response.data;
  } catch (error) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error(error.message || "Failed to sign in with demo account.");
  }
};

export const fetchCurrentUser = async () => {
  try {
    const response = await apiClient.get("/v2/auth/me");
    return response.data?.user || null;
  } catch (error) {
    return null;
  }
};



