/** @type {import('next').NextConfig} */
const nextConfig = {
  // expose backend URL to browser code
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL
  },
  // static export mode
  // output: 'export',
};

export default nextConfig;
