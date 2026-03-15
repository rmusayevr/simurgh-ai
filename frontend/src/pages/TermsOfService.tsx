import { SimurghMark } from '../components/SimurghMark';

export const TermsOfService = () => {

    return (
        <div className="min-h-screen bg-slate-50">
            <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
                <div className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SimurghMark size={28} />
                        <span className="font-black text-lg text-slate-900">
                            Simurgh <span className="text-cyan-600">AI</span>
                        </span>
                    </div>
                </div>
            </nav>

            <main className="max-w-3xl mx-auto px-6 py-12">
                <h1 className="text-4xl font-black text-slate-900 mb-2">Terms of Service</h1>
                <p className="text-sm text-slate-400 mb-10">
                    Last updated: {new Date().toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' })}
                </p>

                <div className="prose prose-slate max-w-none space-y-8 text-slate-700 leading-relaxed">

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">1. Acceptance of Terms</h2>
                        <p>By creating an account and using Simurgh AI, you agree to these Terms of Service. If you do not agree, please do not use the service.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">2. Description of Service</h2>
                        <p>Simurgh AI is an AI-powered platform that helps technical leaders debate architectural decisions, map stakeholders, and support decision-making through a Council of Three AI personas. The service is provided on an "as is" basis and is currently in an early-access phase.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">3. Your Account</h2>
                        <p>You are responsible for maintaining the confidentiality of your login credentials and for all activity that occurs under your account. You must provide accurate information during registration and keep it up to date.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">4. Acceptable Use</h2>
                        <p>You agree not to misuse the service. This includes but is not limited to:</p>
                        <ul className="list-disc pl-6 mt-2 space-y-1">
                            <li>Attempting to access other users' accounts or data</li>
                            <li>Using the service to generate harmful, illegal, or deceptive content</li>
                            <li>Overloading or attempting to circumvent rate limits</li>
                            <li>Reverse-engineering or scraping the platform</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">5. Your Content</h2>
                        <p>You retain ownership of the content and data you submit to Simurgh AI. By submitting content, you grant us a limited licence to process it solely for the purpose of providing the service to you. We do not use your project data to train AI models.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">6. AI-Generated Content</h2>
                        <p>The platform uses AI to generate analysis, proposals, and recommendations. These are provided for informational and decision-support purposes only. You are responsible for reviewing and validating any AI-generated output before acting on it.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">7. Availability</h2>
                        <p>We aim to keep the service available but do not guarantee uninterrupted access. We may modify, suspend, or discontinue the service at any time with reasonable notice where possible.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">8. Limitation of Liability</h2>
                        <p>To the fullest extent permitted by law, Simurgh AI is not liable for any indirect, incidental, or consequential damages arising from your use of the service.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">9. Changes to These Terms</h2>
                        <p>We may update these Terms from time to time. We will notify you of material changes by email or via an in-app notice. Continued use of the service after changes take effect constitutes acceptance of the revised Terms.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">10. Contact</h2>
                        <p>For questions about these Terms, please contact us at <span className="font-semibold text-cyan-600">support@simurgh.ai</span>.</p>
                    </section>

                </div>
            </main>
        </div>
    );
};