import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach JWT Token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('vf_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle Token Refresh on 401
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Do not attempt refresh on auth endpoints
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('vf_refresh_token');
      if (!refreshToken) {
        localStorage.removeItem('vf_access_token');
        localStorage.removeItem('vf_user');
        window.dispatchEvent(new Event('vf-auth-logout'));
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        localStorage.setItem('vf_access_token', data.access_token);
        if (data.refresh_token) {
          localStorage.setItem('vf_refresh_token', data.refresh_token);
        }

        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('vf_access_token');
        localStorage.removeItem('vf_refresh_token');
        localStorage.removeItem('vf_user');
        window.dispatchEvent(new Event('vf-auth-logout'));
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── API Modules ─────────────────────────────────────────────────────────────

export const authAPI = {
  login: async (email, password) => {
    const response = await apiClient.post('/auth/login', { email, password });
    return response.data;
  },
  register: async (email, password, fullName, role = 'operator') => {
    const response = await apiClient.post('/auth/register', {
      email,
      password,
      full_name: fullName,
      role,
    });
    return response.data;
  },
  getMe: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },
};

export const productsAPI = {
  list: async () => {
    const response = await apiClient.get('/products');
    const data = response.data;
    return Array.isArray(data) ? data : (data?.items || []);
  },
  upload: async (formData) => {
    const response = await apiClient.post('/products/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/products/${id}`);
    return response.data;
  },
  delete: async (id) => {
    const response = await apiClient.delete(`/products/${id}`);
    return response.data;
  },
};

export const vendorsAPI = {
  list: async () => {
    const response = await apiClient.get('/vendors');
    return response.data;
  },
  create: async (vendorData) => {
    const response = await apiClient.post('/vendors', vendorData);
    return response.data;
  },
};

export const inspectionsAPI = {
  create: async (formData) => {
    const response = await apiClient.post('/inspections', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/inspections/${id}`);
    return response.data;
  },
  getStatus: async (id) => {
    const response = await apiClient.get(`/inspections/${id}/status`);
    return response.data;
  },
  review: async (id, reviewData) => {
    const response = await apiClient.post(`/inspections/${id}/review`, reviewData);
    return response.data;
  },
};

export const reportsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/reports', { params });
    const data = response.data;
    const items = Array.isArray(data)
      ? data
      : (Array.isArray(data?.items) ? data.items : (Array.isArray(data?.reports) ? data.reports : []));
    return {
      total: data?.total ?? items.length,
      items,
      reports: items,
    };
  },
  get: async (id) => {
    const response = await apiClient.get(`/reports/${id}`);
    return response.data;
  },
  downloadPdfUrl: (id) => `/api/v1/reports/${id}/pdf`,
  downloadPdf: async (id, filename = 'inspection-report.pdf') => {
    const response = await apiClient.get(`/reports/${id}/pdf`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export const analyticsAPI = {
  getSummary: async () => {
    const response = await apiClient.get('/analytics/summary');
    return response.data;
  },
  getByVendor: async () => {
    const response = await apiClient.get('/analytics/by-vendor');
    return response.data?.items || (Array.isArray(response.data) ? response.data : []);
  },
  getByLocation: async () => {
    const response = await apiClient.get('/analytics/by-location');
    return response.data?.items || (Array.isArray(response.data) ? response.data : []);
  },
  getVendorRisk: async () => {
    const response = await apiClient.get('/analytics/vendor-risk');
    return response.data?.items || (Array.isArray(response.data) ? response.data : []);
  },
  getMonthlyTrend: async () => {
    const response = await apiClient.get('/analytics/monthly-trend');
    return response.data?.items || (Array.isArray(response.data) ? response.data : []);
  },
  getByOperator: async () => {
    const response = await apiClient.get('/analytics/by-operator');
    return response.data?.items || (Array.isArray(response.data) ? response.data : []);
  },
};
