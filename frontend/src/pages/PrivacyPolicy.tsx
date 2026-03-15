import { SimurghMark } from '../components/SimurghMark';

export const PrivacyPolicy = () => {

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
                <h1 className="text-4xl font-black text-slate-900 mb-2">Privacy Policy</h1>
                <p className="text-sm text-slate-400 mb-10">
                    Last updated: {new Date().toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' })}
                </p>

                <div className="prose prose-slate max-w-none space-y-8 text-slate-700 leading-relaxed">

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">1. What We Collect</h2>
                        <p>We collect the following personal data when you use Simurgh AI:</p>
                        <ul className="list-disc pl-6 mt-2 space-y-1">
                            <li><strong>Account data:</strong> your name, email address, and job title provided during registration</li>
                            <li><strong>Project data:</strong> content you create within the platform (project descriptions, stakeholder information, proposals)</li>
                            <li><strong>Usage data:</strong> login timestamps, login count, and basic activity metadata</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">2. How We Use Your Data</h2>
                        <p>We use your data solely to provide and improve the service:</p>
                        <ul className="list-disc pl-6 mt-2 space-y-1">
                            <li>To authenticate you and manage your account</li>
                            <li>To process your projects and generate AI analysis</li>
                            <li>To send transactional emails (account verification, password reset)</li>
                            <li>To maintain platform security and prevent abuse</li>
                        </ul>
                        <p className="mt-3">We do not use your project content to train AI models, and we do not sell your data to third parties.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">3. Third-Party Services</h2>
                        <p>Simurgh AI uses the following third-party services to operate:</p>
                        <ul className="list-disc pl-6 mt-2 space-y-1">
                            <li><strong>Anthropic:</strong> AI processing for generating proposals and analysis. Your project content is sent to Anthropic's API for this purpose. See <a href="https://www.anthropic.com/privacy" target="_blank" rel="noopener noreferrer" className="text-cyan-600 hover:underline">Anthropic's Privacy Policy</a>.</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">4. Data Retention</h2>
                        <p>We retain your data for as long as your account is active. You may request deletion of your account and all associated data at any time from your account settings. Upon deletion, your data is permanently removed from our systems.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">5. Your Rights</h2>
                        <p>Under GDPR and applicable data protection law, you have the right to:</p>
                        <ul className="list-disc pl-6 mt-2 space-y-1">
                            <li><strong>Access</strong> the personal data we hold about you</li>
                            <li><strong>Export</strong> your data in a portable format (available in Settings → Data & Privacy)</li>
                            <li><strong>Delete</strong> your account and all associated data (available in Settings → Data & Privacy)</li>
                            <li><strong>Correct</strong> inaccurate data (available in Settings → Profile)</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">6. Security</h2>
                        <p>We use industry-standard security measures including Fernet symmetric encryption for sensitive data at rest, HTTPS in transit, and JWT token-based authentication. Access to your data is restricted to you and platform administrators.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">7. Cookies</h2>
                        <p>We use only essential cookies and local storage required for authentication and session management. We do not use advertising or tracking cookies.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">8. Changes to This Policy</h2>
                        <p>We may update this policy as the service evolves. We will notify you of material changes by email. Continued use of the service after changes take effect constitutes acceptance.</p>
                    </section>

                    <section>
                        <h2 className="text-xl font-black text-slate-900 mb-3">9. Contact</h2>
                        <p>For privacy-related questions or to exercise your rights, contact us at <span className="font-semibold text-cyan-600">privacy@simurgh.ai</span>.</p>
                    </section>

                </div>
            </main>
        </div>
    );
};