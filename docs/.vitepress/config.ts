import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "Sible",
  description: "Lightweight Ansible Orchestrator",
  base: '/Sible/',
  head: [
    ['link', { rel: 'icon', href: '/Sible/favicon.ico' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Sible | Lightweight Ansible Orchestrator' }],
    ['meta', { property: 'og:description', content: 'Sovereign Infrastructure Management for SREs and DevOps.' }],
    ['meta', { property: 'og:image', content: 'https://adam-benyekkou.github.io/Sible/og-image.png' }]
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
        collapsed: false,
        items: [
          { text: 'Philosophy', link: '/guide/philosophy' },
          { text: 'Architecture', link: '/guide/architecture' }
        ]
      },
      {
        text: 'Getting Started',
        collapsed: false,
        items: [
          { text: 'Installation', link: '/guide/installation' },
          { text: 'Onboarding', link: '/guide/onboarding' }
        ]
      },
      {
        text: 'Core Features',
        collapsed: false,
        items: [
          { text: 'Orchestration', link: '/features/orchestration' },
          { text: 'Security & Governance', link: '/features/security' }
        ]
      },
      {
        text: 'Advanced Operations',
        collapsed: false,
        items: [
          { text: 'Automation', link: '/features/automation' },
          { text: 'Recipes', link: '/guide/recipes' }
        ]
      },
      {
        text: 'Operations',
        collapsed: false,
        items: [
          { text: 'Troubleshooting', link: '/guide/troubleshooting' },
          { text: 'Cheat Sheet', link: '/guide/reference' },
          { text: 'REST API', link: '/guide/api' },
          { text: 'Access Guide', link: '/access' }
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/adam-benyekkou/Sible' }
    ],
    footer: {
      message: 'Sovereign Infrastructure Management',
      copyright: 'Copyright © 2026 Sible Team'
    }
  }
})
