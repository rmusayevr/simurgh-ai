import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowRight,
    Users,
    Zap,
    ShieldCheck,
    CheckCircle2,
    Play,
    X,
    BrainCircuit,
    GitMerge,
    BarChart3,
} from 'lucide-react';
import { DashboardMockup } from '../components/LandingVisuals';
import { useAuth } from '../context/AuthContext';
import { SimurghMark } from '../components/SimurghMark';

export const LandingPage = () => {
    const navigate = useNavigate();
    const { isAuthenticated, loading } = useAuth();
    const [isVideoOpen, setIsVideoOpen] = useState(false);

    useEffect(() => {
        if (!loading && isAuthenticated) {
            navigate('/dashboard');
        }
    }, [isAuthenticated, loading, navigate]);

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="w-12 h-12 border-4 border-cyan-600 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 font-sans text-slate-900">

            {/* ── NAV BAR ── */}
            <nav className="fixed w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <SimurghMark size={34} />
                        <span className="font-black text-xl tracking-tight text-slate-900">
                            Simurgh <span className="text-cyan-600">AI</span>
                        </span>
                    </div>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => navigate('/login')}
                            className="text-sm font-bold text-slate-600 hover:text-cyan-600 transition"
                        >
                            Sign In
                        </button>
                        <button
                            onClick={() => navigate('/register')}
                            className="bg-slate-900 text-white px-5 py-2 rounded-full text-sm font-bold hover:bg-slate-800 transition shadow-lg hover:shadow-xl"
                        >
                            Get Started
                        </button>
                    </div>
                </div>
            </nav>

            {/* ── HERO ── */}
            <section className="pt-32 pb-20 px-6 relative overflow-hidden">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-cyan-100/40 rounded-full blur-3xl -z-10 opacity-60" />

                <div className="max-w-4xl mx-auto text-center">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-50 text-cyan-700 text-xs font-bold uppercase tracking-wider mb-6 border border-cyan-100 animate-in fade-in slide-in-from-bottom-4 duration-700">
                        <Zap size={12} fill="currentColor" />
                        Mission Control for Solution Architects
                    </div>

                    <h1 className="text-5xl md:text-7xl font-black text-slate-900 mb-6 tracking-tight leading-tight animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
                        Three Perspectives.<br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 to-indigo-600">
                            One Decision.
                        </span>
                    </h1>

                    <p className="text-lg md:text-xl text-slate-500 mb-10 max-w-2xl mx-auto leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
                        A Council of Three AI personas debates every architectural decision from conflicting angles — then produces three stress-tested proposals grounded in your actual project documents.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-300">
                        <button
                            onClick={() => navigate('/register')}
                            className="w-full sm:w-auto px-8 py-4 bg-cyan-600 text-white rounded-xl font-bold text-lg hover:bg-cyan-700 transition shadow-xl shadow-cyan-200 flex items-center justify-center gap-2"
                        >
                            Start for Free <ArrowRight size={20} />
                        </button>
                        <button
                            onClick={() => setIsVideoOpen(true)}
                            className="w-full sm:w-auto px-8 py-4 bg-white text-slate-700 border border-slate-200 rounded-xl font-bold text-lg hover:bg-slate-50 transition flex items-center justify-center gap-2 group"
                        >
                            <div className="w-6 h-6 rounded-full bg-cyan-100 flex items-center justify-center text-cyan-600 group-hover:bg-cyan-600 group-hover:text-white transition-colors">
                                <Play size={10} fill="currentColor" />
                            </div>
                            Watch Demo
                        </button>
                    </div>
                </div>
            </section>

            {/* ── UI PREVIEW MOCKUP ── */}
            <section className="px-6 pb-20">
                <div className="max-w-5xl mx-auto transform hover:scale-[1.01] transition-transform duration-700">
                    <DashboardMockup />
                </div>
            </section>

            {/* ── FEATURES ── */}
            <section className="py-24 bg-white">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl font-black text-slate-900 mb-4">Why Simurgh AI</h2>
                        <p className="text-slate-500 max-w-2xl mx-auto">
                            Named after the mythical bird of Azerbaijani legend — a being said to have witnessed the world three times over, giving it total perspective. Your decisions deserve the same.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        <FeatureCard
                            icon={<BrainCircuit className="text-cyan-600" size={24} />}
                            title="Council of Three AI Agents"
                            desc="Legacy Keeper, Innovator, and Mediator debate your architecture for up to 6 turns before each writing their own complete proposal."
                        />
                        <FeatureCard
                            icon={<Users className="text-cyan-600" size={24} />}
                            title="Stakeholder Political Map"
                            desc="Visualise who holds influence and who is blocking progress with the Mendelow Power/Interest Matrix. Spot risks before they derail your timeline."
                        />
                        <FeatureCard
                            icon={<GitMerge className="text-violet-600" size={24} />}
                            title="Consensus Detection"
                            desc="When all three personas converge, the debate ends early. You get a synthesis document — not just three opinions, but a path forward."
                        />
                        <FeatureCard
                            icon={<BarChart3 className="text-emerald-600" size={24} />}
                            title="Project Health Dashboard"
                            desc="Political Risk Score, Strategic Readiness Index, and stakeholder sentiment tracked from Champion to Blocker — all in one view."
                        />
                        <FeatureCard
                            icon={<Zap className="text-amber-500" size={24} />}
                            title="Grounded in Your Documents"
                            desc="Upload project PDFs and every proposal is grounded in your actual constraints — not generic best practices. RAG runs locally, no OpenAI needed."
                        />
                        <FeatureCard
                            icon={<ShieldCheck className="text-emerald-600" size={24} />}
                            title="Secure & Private"
                            desc="Sensitive stakeholder data is encrypted at rest. Self-hosted — your strategic intelligence never leaves your own infrastructure."
                        />
                    </div>
                </div>
            </section>

            {/* ── VALUE PILLARS ── */}
            <section className="py-20 bg-slate-50 border-y border-slate-200">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <p className="text-xs font-black uppercase tracking-widest text-cyan-600 mb-10">Built for technical leaders</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        <Pillar icon="🏗️" label="Architecture-first" desc="Designed around how architects actually think" />
                        <Pillar icon="⚡" label="AI-powered" desc="Claude-driven multi-agent debate engine" />
                        <Pillar icon="🔒" label="Private by default" desc="Self-hosted. Your data never leaves your infrastructure." />
                        <Pillar icon="🎯" label="Decision-ready" desc="Three structured proposals you can act on immediately" />
                    </div>
                </div>
            </section>

            {/* ── CTA ── */}
            <section className="py-24 bg-slate-900 text-white text-center px-6">
                <div className="max-w-3xl mx-auto">
                    <div className="flex justify-center mb-6">
                        <SimurghMark size={56} />
                    </div>
                    <h2 className="text-3xl md:text-4xl font-black mb-6">Ready to lead with confidence?</h2>
                    <p className="text-slate-400 mb-10 text-lg">
                        Join solution architects, product managers, and engineering leads who walk into the room with three stress-tested positions instead of one.
                    </p>
                    <button
                        onClick={() => navigate('/register')}
                        className="px-8 py-4 bg-cyan-500 text-white rounded-xl font-bold text-lg hover:bg-cyan-400 transition shadow-lg shadow-cyan-900/50"
                    >
                        Create Free Account
                    </button>
                    <p className="mt-6 text-sm text-slate-500 flex items-center justify-center gap-2">
                        <CheckCircle2 size={16} className="text-emerald-500" /> No credit card required
                        <span className="mx-2">•</span>
                        <CheckCircle2 size={16} className="text-emerald-500" /> Self-hosted, open source
                    </p>
                </div>
            </section>

            {/* ── FOOTER ── */}
            <footer className="bg-slate-950 py-8 text-center text-slate-600 text-sm">
                <div className="flex items-center justify-center gap-2 mb-3">
                    <SimurghMark size={20} />
                    <span className="text-slate-500 font-bold">Simurgh AI</span>
                </div>
                <p>&copy; {new Date().getFullYear()} Simurgh AI. All rights reserved.</p>
                <div className="flex items-center justify-center gap-6 mt-3">
                    <a href="/terms" className="hover:text-slate-400 transition-colors">Terms of Service</a>
                    <a href="/privacy" className="hover:text-slate-400 transition-colors">Privacy Policy</a>
                </div>
            </footer>

            {/* ── VIDEO MODAL ── */}
            {isVideoOpen && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="relative w-full max-w-4xl bg-black rounded-2xl overflow-hidden shadow-2xl aspect-video animate-in zoom-in-95 duration-200">
                        <button
                            onClick={() => setIsVideoOpen(false)}
                            className="absolute top-4 right-4 z-10 w-10 h-10 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center transition"
                        >
                            <X size={20} />
                        </button>
                        <div className="w-full h-full flex items-center justify-center bg-slate-800 text-slate-500">
                            {/* Replace with YouTube embed once video is ready:
                                <iframe
                                    className="w-full h-full"
                                    src="https://www.youtube.com/embed/YOUR_VIDEO_ID?autoplay=1"
                                    allow="autoplay; encrypted-media"
                                    allowFullScreen
                                />
                            */}
                            <div className="text-center">
                                <Play size={64} className="mx-auto mb-4 opacity-50" />
                                <p>Demo video coming soon</p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const FeatureCard = ({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) => (
    <div className="p-8 bg-slate-50 rounded-2xl border border-slate-100 hover:border-cyan-100 hover:shadow-xl hover:shadow-cyan-100/50 transition-all duration-300 group">
        <div className="w-12 h-12 bg-white rounded-xl border border-slate-200 flex items-center justify-center mb-6 shadow-sm group-hover:scale-110 transition-transform">
            {icon}
        </div>
        <h3 className="text-xl font-bold text-slate-900 mb-3">{title}</h3>
        <p className="text-slate-500 leading-relaxed">{desc}</p>
    </div>
);

const Pillar = ({ icon, label, desc }: { icon: string; label: string; desc: string }) => (
    <div className="flex flex-col items-center text-center gap-2">
        <div className="text-3xl mb-1">{icon}</div>
        <div className="text-sm font-black text-slate-900">{label}</div>
        <div className="text-xs text-slate-500 leading-relaxed">{desc}</div>
    </div>
);