import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { Image, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
} from '../components/price-check/priceCheckLocationTokens';
import { colors } from '../constants/theme';

const LOGO_IMAGE = require('../../assets/images/brand/wisebasket-logo-horizontal.png');
const HERO_IMAGE = require('../../assets/images/auth/auth-basket-hero.png');
const PLANT_LEFT_TOP_IMAGE = require('../../assets/images/auth/auth-plant-left-top.png');
const PLANT_RIGHT_MIDDLE_IMAGE = require('../../assets/images/auth/auth-plant-right-middle.png');
const PLANT_BOTTOM_LEFT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-left.png');
const PLANT_BOTTOM_RIGHT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-right.png');

interface WelcomeScreenProps {
  onContinue: () => void;
  onLogin?: () => void;
  onRegister?: () => void;
}

interface AuthActionButtonProps {
  label: string;
  onPress: () => void;
  primary?: boolean;
}

function DecorativeLayer({ height, width }: { height: number; width: number }) {
  const plantLeftTopWidth = Math.min(width * 0.31, 132);
  const plantRightMiddleWidth = Math.min(width * 0.25, 108);
  const plantBottomLeftWidth = Math.min(width * 0.23, 94);
  const plantBottomRightWidth = Math.min(width * 0.44, 180);

  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.decorativeLayer]}>
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={PLANT_LEFT_TOP_IMAGE}
        style={[
          styles.plant,
          styles.plantLeftTop,
          {
            height: plantLeftTopWidth * (1024 / 1536),
            top: height * 0.15,
            width: plantLeftTopWidth,
          },
        ]}
      />
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={PLANT_RIGHT_MIDDLE_IMAGE}
        style={[
          styles.plant,
          styles.plantRightMiddle,
          {
            height: plantRightMiddleWidth * (1585 / 992),
            top: height * 0.27,
            width: plantRightMiddleWidth,
          },
        ]}
      />
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={PLANT_BOTTOM_LEFT_IMAGE}
        style={[
          styles.plant,
          styles.plantBottomLeft,
          {
            bottom: -height * 0.01,
            height: plantBottomLeftWidth * (1535 / 1024),
            width: plantBottomLeftWidth,
          },
        ]}
      />
      <Image
        accessibilityElementsHidden
        resizeMode="contain"
        source={PLANT_BOTTOM_RIGHT_IMAGE}
        style={[
          styles.plant,
          styles.plantBottomRight,
          {
            bottom: -height * 0.01,
            height: plantBottomRightWidth * (1024 / 1536),
            width: plantBottomRightWidth,
          },
        ]}
      />
    </View>
  );
}

function AuthActionButton({ label, onPress, primary = false }: AuthActionButtonProps) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionButton,
        primary ? styles.primaryAction : styles.secondaryAction,
        pressed && styles.actionPressed,
      ]}
    >
      <Text style={[styles.actionLabel, primary ? styles.primaryActionLabel : styles.secondaryActionLabel]}>
        {label}
      </Text>
      <MaterialCommunityIcons
        color={primary ? colors.white : colors.greenDeep}
        name="chevron-right"
        size={36}
        style={styles.actionIcon}
      />
    </Pressable>
  );
}

/** Static Auth Entry composition. Auth behaviour is supplied by the existing callbacks. */
export function WelcomeScreen({ onContinue, onLogin = () => undefined, onRegister = onContinue }: WelcomeScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const { height, width } = useWindowDimensions();
  const horizontalPadding = width < 376 ? 20 : width < 404 ? 22 : 24;
  const compactHeight = height < 820;
  const compactWidth = width <= 384;
  const logoWidth = Math.min(width * 0.7, 288);
  // The repaired hero includes the full right heart and right-side accents.
  // The wider transparent canvas keeps the basket/character at its prior visual scale.
  const heroWidth = Math.min(width * 0.77, 316);
  const logoHeight = logoWidth * (389 / 1528);
  const heroHeight = heroWidth * (520 / 647);

  if (!fontsLoaded) {
    return <View style={styles.wrapper} />;
  }

  return (
    <View style={styles.wrapper}>
      <DecorativeLayer height={height} width={width} />
      <View
        style={[
          styles.content,
          {
            paddingHorizontal: horizontalPadding,
            paddingTop: compactHeight ? 10 : 16,
          },
        ]}
      >
        <View style={styles.contentLayer}>
          <Image
            accessibilityLabel="WiseBasket"
            resizeMode="contain"
            source={LOGO_IMAGE}
            style={[styles.logo, { height: logoHeight, width: logoWidth }]}
          />

          <Image
            accessibilityLabel="WiseBasket basket character filled with fresh vegetables"
            resizeMode="contain"
            source={HERO_IMAGE}
            style={[
              styles.hero,
              {
                height: heroHeight,
                marginTop: compactHeight ? 4 : 8,
                width: heroWidth,
              },
            ]}
          />

          <View style={[styles.copyBlock, { marginTop: compactHeight ? 5 : 8 }]}>
            <Text
              accessibilityRole="header"
              style={[styles.title, compactWidth ? styles.compactTitle : undefined]}
            >
              Save and continue
            </Text>
            <Text style={styles.description}>Log in or create an account to keep going.</Text>
          </View>

          <View style={[styles.actions, { marginTop: compactHeight ? 12 : 20 }]}>
            <AuthActionButton label="Create account" onPress={onRegister} primary />
            <AuthActionButton label="Log in" onPress={onLogin} />
          </View>

          <View style={[styles.privacyRow, { marginTop: compactHeight ? 14 : 18 }]}>
            <MaterialCommunityIcons
              accessibilityElementsHidden
              color={colors.green}
              name="shield-lock"
              size={36}
            />
            <Text style={styles.privacyText}>Your information stays private and secure.</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  actionButton: {
    alignItems: 'center',
    borderRadius: 32,
    flexDirection: 'row',
    justifyContent: 'center',
    minHeight: 56,
    overflow: 'hidden',
    paddingHorizontal: 20,
    position: 'relative',
    width: '100%',
  },
  actionIcon: {
    position: 'absolute',
    right: 18,
  },
  actionLabel: {
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 21,
    fontWeight: '600',
    lineHeight: 28,
    textAlign: 'center',
  },
  actionPressed: {
    opacity: 0.82,
  },
  actions: {
    gap: 16,
    width: '100%',
  },
  content: {
    flex: 1,
    paddingBottom: 16,
    paddingTop: 18,
  },
  contentLayer: {
    alignItems: 'center',
    alignSelf: 'stretch',
    position: 'relative',
    zIndex: 1,
  },
  copyBlock: {
    alignItems: 'center',
    width: '100%',
  },
  decorativeLayer: {
    pointerEvents: 'none',
    zIndex: 0,
  },
  description: {
    color: '#4B7580',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 18,
    fontWeight: '400',
    lineHeight: 26,
    marginTop: 6,
    textAlign: 'center',
  },
  hero: {
    maxWidth: 316,
  },
  logo: {
    maxWidth: 296,
  },
  plant: {
    position: 'absolute',
  },
  plantBottomLeft: {
    left: '-4%',
  },
  plantBottomRight: {
    right: '-4%',
  },
  plantLeftTop: {
    left: '-14%',
  },
  plantRightMiddle: {
    right: '-9%',
  },
  primaryAction: {
    backgroundColor: '#087B6F',
  },
  primaryActionLabel: {
    color: colors.white,
  },
  privacyRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'center',
    marginTop: 28,
    maxWidth: 340,
    minHeight: 48,
    width: '100%',
  },
  privacyText: {
    color: '#4B7580',
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 22,
  },
  secondaryAction: {
    backgroundColor: 'rgba(254, 253, 250, 0.82)',
    borderColor: '#086C67',
    borderWidth: 2,
  },
  secondaryActionLabel: {
    color: '#0A4E50',
  },
  title: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 36,
    fontWeight: '700',
    lineHeight: 42,
    textAlign: 'center',
  },
  compactTitle: {
    fontSize: 34,
    lineHeight: 40,
  },
  wrapper: {
    backgroundColor: '#FEFDFA',
    flex: 1,
    overflow: 'hidden',
  },
});
