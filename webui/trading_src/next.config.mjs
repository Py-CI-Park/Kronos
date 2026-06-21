/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  assetPrefix: process.env.KRONOS_TRADING_ASSET_PREFIX ?? '/trading-static',
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
