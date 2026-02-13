import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "Sible",
  description: "Lightweight Ansible Orchestrator",
  base: '/sible/',
  head: [
    ['link', { rel: 'icon', href: '/sible/favicon.ico' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Sible | Lightweight Ansible Orchestrator' }],
    ['meta', { property: 'og:description', content: 'Sovereign Infrastructure Management for SREs and DevOps.' }],
    ['meta', { property: 'og:image', content: 'https://your-org.github.io/sible/og-image.png' }]
  ],
  themeConfig: {
    logo: '/logo.png',
    nav: [
      { text: 'Guide', link: '/guide/onboarding' },
      { text: 'Features', link: '/features/orchestration' }
    ],
    sidebar: [
      {
        text: 'Introduction',
        collapsible: true,
        items: [
          { text: 'Philosophy', link: '/guide/philosophy' },
          { text: 'Architecture', link: '/guide/architecture' }
        ]
      },
      {
        text: 'Getting Started',
        collapsible: true,
        items: [
          { text: 'Installation', link: '/guide/installation' },
          { text: 'Onboarding', link: '/guide/onboarding' }
        ]
      },
      {
        text: 'Core Features',
        collapsible: true,
        items: [
          { text: 'Orchestration', link: '/features/orchestration' },
          { text: 'Security & Governance', link: '/features/security' }
        ]
      },
      {
        text: 'Advanced Operations',
        collapsible: true,
        items: [
          { text: 'Automation', link: '/features/automation' },
          { text: 'Recipes', link: '/guide/recipes' }
        ]
      },
      {
        text: 'Operations',
        collapsible: true,
        items: [
          { text: 'Troubleshooting', link: '/guide/troubleshooting' },
          { text: 'Cheat Sheet', link: '/guide/reference' },
          { text: 'Access Guide', link: '/access' }
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/your-org/sible' }
    ],
    footer: {
      message: 'Sovereign Infrastructure Management',
      copyright: 'Copyright © 2026 Sible Team'
    }
  }
})
