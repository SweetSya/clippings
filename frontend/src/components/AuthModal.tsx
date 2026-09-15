import React, { useState, useEffect } from 'react';
import { Lock, KeyRound, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { authApi } from '../services/api';

interface AuthModalProps {
  isConfigured: boolean;
  onSuccess: (token: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isConfigured, onSuccess }) => {
  const [isSetup, setIsSetup] = useState(!isConfigured);
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setIsSetup(!isConfigured);
  }, [isConfigured]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (pin.length < 4 || pin.length > 8 || !/^\d+$/.test(pin)) {
      setError('PIN harus berupa 4 sampai 8 digit angka numerik.');
      return;
    }

    if (isSetup && pin !== confirmPin) {
      setError('Konfirmasi PIN tidak cocok. Silakan ulangi.');
      return;
    }

    setLoading(true);
    try {
      if (isSetup) {
        const res = await authApi.setup(pin);
        authApi.setToken(res.token);
        onSuccess(res.token);
      } else {
        const res = await authApi.login(pin);
        authApi.setToken(res.token);
        onSuccess(res.token);
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || 'Terjadi kesalahan pada autentikasi.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const appendDigit = (digit: string) => {
    if (pin.length < 8) {
      setPin((prev) => prev + digit);
    }
  };

  const backspace = () => {
    setPin((prev) => prev.slice(0, -1));
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#1C1917]/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#F5F5F4] border border-[#D6D3D1] rounded-2xl shadow-2xl max-w-sm w-full p-6 text-center animate-in fade-in zoom-in-95 duration-200">
        <div className="w-14 h-14 bg-[#C2410C]/10 text-[#C2410C] rounded-2xl flex items-center justify-center mx-auto mb-4 border border-[#C2410C]/20 shadow-inner">
          {isSetup ? <KeyRound className="w-7 h-7" /> : <Lock className="w-7 h-7" />}
        </div>

        <h2 className="font-display font-bold text-2xl text-[#1C1917]">
          {isSetup ? 'Inisialisasi PIN Sistem' : 'Buka Kunci Akses'}
        </h2>
        <p className="text-sm text-[#57534E] mt-1 mb-5">
          {isSetup
            ? 'Buat 4-8 digit PIN untuk mengamankan instance lokal Anda.'
            : 'Masukkan PIN Anda untuk mengelola video dan rendering shorts.'}
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center space-x-2 text-left">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="password"
              inputMode="numeric"
              maxLength={8}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              placeholder="Masukkan PIN (4-8 Digit)"
              className="w-full text-center tracking-[0.4em] text-2xl font-mono py-3 bg-white border border-[#D6D3D1] rounded-xl focus:border-[#C2410C] focus:ring-2 focus:ring-[#C2410C]/20 outline-none transition-all"
              autoFocus
            />
          </div>

          {isSetup && (
            <div>
              <input
                type="password"
                inputMode="numeric"
                maxLength={8}
                value={confirmPin}
                onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ''))}
                placeholder="Konfirmasi PIN"
                className="w-full text-center tracking-[0.4em] text-2xl font-mono py-3 bg-white border border-[#D6D3D1] rounded-xl focus:border-[#C2410C] focus:ring-2 focus:ring-[#C2410C]/20 outline-none transition-all"
              />
            </div>
          )}

          {/* Numeric Keypad Buttons */}
          <div className="grid grid-cols-3 gap-2 pt-2">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9', 'C', '0', '←'].map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => {
                  if (key === 'C') setPin('');
                  else if (key === '←') backspace();
                  else appendDigit(key);
                }}
                className="py-2.5 bg-white hover:bg-[#E7E5E4] text-[#1C1917] font-semibold text-lg rounded-xl border border-[#D6D3D1] active:scale-95 transition-all shadow-xs"
              >
                {key}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || pin.length < 4}
            className="w-full py-3 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold rounded-xl shadow-md shadow-[#C2410C]/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-2 flex items-center justify-center space-x-2"
          >
            <CheckCircle2 className="w-5 h-5" />
            <span>{loading ? 'Memverifikasi...' : isSetup ? 'Simpan PIN & Masuk' : 'Buka Dashboard'}</span>
          </button>
        </form>
      </div>
    </div>
  );
};
