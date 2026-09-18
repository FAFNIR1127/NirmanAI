import React, { useState } from 'react';
import {
  Shield,
  Lock,
  User,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  Building2,
  ArrowRight,
  Sparkles,
  KeyRound,
  ShieldCheck,
  Cpu
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please provide both username and password.');
      return;
    }
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Authentication failed. Please verify credentials.');
    }
  };

  const handleQuickDemoLogin = async () => {
    setError(null);
    try {
      await login('admin', 'admin123');
    } catch (err: any) {
      setError('Quick Demo Login failed.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-900 text-slate-100 font-sans selection:bg-blue-600 selection:text-white relative overflow-hidden">
      {/* Background Subtle Gradient Blobs */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Top Govt of India Strip */}
      <div className="bg-slate-950 border-b border-slate-800 py-1.5 px-4 text-[11px] flex justify-between items-center text-slate-400">
        <div className="max-w-7xl mx-auto w-full flex justify-between items-center px-4">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500"></span>
            <span className="font-medium tracking-wide">
              GOVERNMENT OF INDIA &bull; MINISTRY OF STATISTICS &amp; PROGRAMME IMPLEMENTATION
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-slate-400">
            <span className="flex items-center gap-1 text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" /> Official Infrastructure Surveillance System
            </span>
            <span>IPMD / PAIMANA Security Division</span>
          </div>
        </div>
      </div>

      {/* Main Login Card Section */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 z-10">
        <div className="w-full max-w-md bg-slate-800/90 backdrop-blur-xl border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden">
          
          {/* Header Banner */}
          <div className="p-6 sm:p-8 border-b border-slate-700/60 bg-gradient-to-b from-slate-800/80 to-slate-800/40 text-center relative">
            {/* National Emblem Badge */}
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-gov-navy border border-blue-400/40 shadow-lg shadow-blue-500/20 mb-3">
              <span className="font-extrabold text-2xl text-white tracking-wider">N</span>
            </div>
            
            <h1 className="text-2xl font-black tracking-tight text-white flex items-center justify-center gap-2">
              NIRMAN
              <span className="bg-gov-amber/20 text-gov-amber border border-gov-amber/40 text-[10px] font-bold px-2 py-0.5 rounded tracking-wider uppercase">
                PAIMANA AI
              </span>
            </h1>
            
            <p className="text-xs text-slate-400 mt-1 font-medium">
              National Infrastructure Risk Monitoring &amp; Analytics Network
            </p>
            <p className="text-[11px] text-blue-400 mt-0.5 font-mono">
              Authorised Government Personnel &bull; Executive Portal
            </p>
          </div>

          {/* Login Form Body */}
          <div className="p-6 sm:p-8 space-y-5">
            {error && (
              <div className="p-3.5 bg-red-950/70 border border-red-800/80 rounded-xl text-xs text-red-200 flex items-start gap-2.5 animate-shake">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div className="flex-1 font-medium">{error}</div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username Input */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Admin ID or Official Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. admin or officer@mospi.gov.in"
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-900/90 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    required
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Security Password
                  </label>
                  <span className="text-[10px] text-slate-400 font-mono">Protected by 256-Bit SHA</span>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter security key or password"
                    className="w-full pl-10 pr-10 py-2.5 bg-slate-900/90 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-blue-600/30 transition flex items-center justify-center gap-2 group disabled:opacity-50"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Verifying Credentials...
                  </span>
                ) : (
                  <>
                    <span>Sign In to Executive Dashboard</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" />
                  </>
                )}
              </button>
            </form>

            {/* Quick Demo Access Divider */}
            <div className="relative my-4 text-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-700/80"></div>
              </div>
              <span className="relative px-3 bg-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Instant Reviewer Access
              </span>
            </div>

            {/* One-Click Quick Demo Login Button */}
            <button
              onClick={handleQuickDemoLogin}
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/80 text-emerald-400 hover:text-emerald-300 text-xs font-bold rounded-xl transition flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>One-Click Authorised Admin Demo Login</span>
            </button>

            {/* Officer Persona Note */}
            <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Default Officer Profile:
              </div>
              <div className="font-mono text-[10px] text-slate-400">
                Dr. Rajeshwar Sharma, IAS (Joint Secretary &bull; MoSPI IPMD)
              </div>
              <div className="text-[10px] text-slate-500">
                Credentials: <code className="text-blue-300">admin</code> / <code className="text-blue-300">admin123</code>
              </div>
            </div>
          </div>

          {/* Footer Security Notice */}
          <div className="px-6 py-3 bg-slate-950/60 border-t border-slate-800 text-center text-[10px] text-slate-500 font-mono">
            CONFIDENTIAL &bull; FOR USE BY AUTHORISED CENTRAL MINISTRY OFFICIALS ONLY
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
