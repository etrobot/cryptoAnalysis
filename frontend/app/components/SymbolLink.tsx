import React from 'react'

interface SymbolLinkProps {
  symbol: string
  name?: string
  className?: string
}

function getBybitUrl(symbol: string) {
  // Assuming the symbol is in the format BASEQUOTE, e.g., BTCUSDT
  const quote = "USDT";
  if (symbol.endsWith(quote)) {
    const base = symbol.substring(0, symbol.length - quote.length);
    return `https://www.bybit.com/trade/spot/${base}/${quote}`;
  }
  // Fallback for symbols that don't end with USDT
  return `https://www.bybit.com/trade/spot/${symbol}`;
}

export function SymbolLink({ symbol, name, className = '' }: SymbolLinkProps) {
  return (
    <a
      href={getBybitUrl(symbol)}
      target="_blank"
      rel="noopener noreferrer"
      className={`hover:text-blue-600 hover:underline ${className}`}
    >
      <div className="font-medium">{name || symbol}</div>
      <div className="text-xs text-muted-foreground font-mono">{symbol}</div>
    </a>
  )
}