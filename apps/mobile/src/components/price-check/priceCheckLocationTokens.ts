export const priceCheckLocationFonts = {
  heading: 'PriceCheckFredokaBold',
  cardTitle: 'PriceCheckFredokaSemiBold',
  body: 'PriceCheckNunitoRegular',
  bodySemibold: 'PriceCheckNunitoSemiBold',
} as const;

export const priceCheckLocationFontAssets = {
  PriceCheckFredokaBold: require('../../../assets/fonts/Fredoka-Bold.ttf'),
  PriceCheckFredokaSemiBold: require('../../../assets/fonts/Fredoka-SemiBold.ttf'),
  PriceCheckNunitoRegular: require('../../../assets/fonts/Nunito-Regular.ttf'),
  PriceCheckNunitoSemiBold: require('../../../assets/fonts/Nunito-SemiBold.ttf'),
} as const;

export const priceCheckLocationTokens = {
  colors: {
    background: '#FEFDFA',
    deepTeal: '#012C2D',
    green: '#1B713B',
    orange: '#FF640B',
    cardCream: '#FDF6E9',
    primaryText: '#012C2D',
    secondaryText: '#486264',
    transparent: 'transparent',
  },
  fonts: priceCheckLocationFonts,
  spacing: {
    headerHeight: 84,
    pageHorizontal: 24,
    pageHorizontalCompact: 20,
    headingTop: 26,
    descriptionTop: 16,
    heroTop: 6,
    heroHeight: 250,
    cardsTop: 4,
    cardGap: 14,
    cardHorizontalInset: 8,
    cardPaddingHorizontal: 12,
    cardPaddingVertical: 10,
    cardInnerGap: 8,
    cardTitleSubtitleGap: 4,
  },
  radius: {
    card: 26,
  },
  shadow: {
    color: '#7D6D52',
    offset: { width: 0, height: 4 },
    opacity: 0.1,
    radius: 10,
    elevation: 2,
  },
  iconSizes: {
    touchTarget: 48,
    artworkWidth: 104,
    artworkHeight: 68,
    chevron: 34,
    titleAccentWidth: 32,
    titleAccentHeight: 58,
  },
} as const;
