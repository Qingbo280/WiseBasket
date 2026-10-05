import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useState, type ComponentProps, type ReactNode } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
} from '../components/price-check/priceCheckLocationTokens';

const LOGO_IMAGE = require('../../assets/images/brand/wisebasket-logo-horizontal.png');
const HERO_IMAGE = require('../../assets/images/auth/login-hero-basket.png');
const PLANT_LEFT_TOP_IMAGE = require('../../assets/images/auth/auth-plant-left-top.png');
const PLANT_RIGHT_MIDDLE_IMAGE = require('../../assets/images/auth/auth-plant-right-middle.png');
const PLANT_BOTTOM_LEFT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-left.png');
const PLANT_BOTTOM_RIGHT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-right.png');

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginEntryScreenProps {
  loginError?: string | null;
  onCreateAccount?: () => void;
  onForgotPassword?: () => void;
  onLogin?: (credentials: LoginCredentials) => void | Promise<void>;
}

function DecorativeLayer({ height, width }: { height: number; width: number }) {
  const plantLeftTopWidth = Math.min(width * 0.31, 132);
  const plantRightMiddleWidth = Math.min(width * 0.22, 90);
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
            top: height * 0.31,
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

interface LoginFieldProps {
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  icon: ComponentProps<typeof MaterialCommunityIcons>['name'];
  keyboardType?: 'default' | 'email-address';
  onChangeText: (value: string) => void;
  placeholder: string;
  secureTextEntry?: boolean;
  trailing?: ReactNode;
  value: string;
}

function LoginField({
  autoCapitalize = 'none',
  icon,
  keyboardType = 'default',
  onChangeText,
  placeholder,
  secureTextEntry = false,
  trailing,
  value,
}: LoginFieldProps) {
  return (
    <View style={styles.field}>
      <MaterialCommunityIcons
        accessibilityElementsHidden
        color="#69749D"
        name={icon}
        size={30}
        style={styles.fieldIcon}
      />
      <TextInput
        accessibilityLabel={placeholder}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
        keyboardType={keyboardType}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#69749D"
        secureTextEntry={secureTextEntry}
        style={styles.input}
        value={value}
      />
      {trailing}
    </View>
  );
}

/** Static Login composition. Callbacks are intentionally UI-only in this pass. */
export function LoginEntryScreen({
  loginError = null,
  onCreateAccount = () => undefined,
  onForgotPassword = () => undefined,
  onLogin = () => undefined,
}: LoginEntryScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleLogin = async () => {
    if (busy) return;
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setValidationError('Enter your email and password.');
      return;
    }
    setValidationError(null);
    setBusy(true);
    try {
      await onLogin({ email: trimmedEmail, password });
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : 'Login failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const { height, width } = useWindowDimensions();
  const horizontalPadding = width <= 360 ? 24 : width <= 384 ? 28 : 34;
  const compactHeight = height < 840;
  const logoWidth = Math.min(width * 0.56, 232);
  const heroWidth = Math.min(width * 0.75, 310);
  const heroHeight = heroWidth * (897 / 1304);

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  return (
    <View style={styles.wrapper}>
      <DecorativeLayer height={height} width={width} />
      <ScrollView
        bounces={false}
        contentContainerStyle={[
          styles.content,
          {
            minHeight: height,
            paddingHorizontal: horizontalPadding,
            paddingTop: compactHeight ? 24 : 52,
          },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.contentLayer}>
          <Image
            accessibilityLabel="WiseBasket"
            resizeMode="contain"
            source={LOGO_IMAGE}
            style={{
              height: logoWidth * (389 / 1528),
              width: logoWidth,
            }}
          />

          <Image
            accessibilityLabel="WiseBasket basket character with vegetables and a green check badge"
            resizeMode="contain"
            source={HERO_IMAGE}
            style={[
              styles.hero,
              {
                height: heroHeight,
                marginTop: compactHeight ? 18 : 24,
                width: heroWidth,
              },
            ]}
          />

          <View style={styles.titleBlock}>
            <Text accessibilityRole="header" style={styles.title}>
              Log in
            </Text>
            <Text style={styles.supportingCopy}>Welcome back. Continue your plan anytime.</Text>
          </View>

          <View style={[styles.form, { marginTop: compactHeight ? 14 : 18 }]}>
            <LoginField
              icon="email-outline"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="Email address"
              value={email}
            />
            <LoginField
              icon="lock"
              onChangeText={setPassword}
              placeholder="Password"
              secureTextEntry={!showPassword}
              trailing={(
                <Pressable
                  accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
                  accessibilityRole="button"
                  hitSlop={4}
                  onPress={() => setShowPassword((visible) => !visible)}
                  style={styles.eyeButton}
                >
                  <MaterialCommunityIcons
                    color="#69749D"
                    name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    size={29}
                  />
                </Pressable>
              )}
              value={password}
            />
          </View>

          <Pressable
            accessibilityLabel="Forgot password?"
            accessibilityRole="button"
            onPress={onForgotPassword}
            style={styles.forgotPassword}
          >
            <Text style={styles.forgotPasswordLabel}>Forgot password?</Text>
          </Pressable>

          <Pressable
            accessibilityLabel="Log in"
            accessibilityRole="button"
            accessibilityState={{ busy }}
            disabled={busy}
            onPress={() => void handleLogin()}
            style={({ pressed }) => [styles.loginButton, pressed && styles.pressed]}
          >
            <Text style={styles.loginButtonLabel}>
              {busy ? 'Logging in…' : 'Log in'}
            </Text>
          </Pressable>
          {validationError || loginError ? (
            <Text style={styles.errorText}>{validationError ?? loginError}</Text>
          ) : null}

          <Pressable
            accessibilityLabel="Create account"
            accessibilityRole="button"
            onPress={onCreateAccount}
            style={styles.createAccountLink}
          >
            <Text style={styles.createAccountText}>
              Don’t have an account?{' '}
              <Text style={styles.createAccountEmphasis}>Create account</Text>
            </Text>
          </Pressable>

          <View style={styles.privacyRow}>
            <MaterialCommunityIcons
              accessibilityElementsHidden
              color="#3F9B50"
              name="shield-check"
              size={38}
            />
            <Text style={styles.privacyText}>Your information stays private and secure.</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingBottom: 24,
  },
  contentLayer: {
    alignItems: 'center',
    alignSelf: 'stretch',
    position: 'relative',
    zIndex: 1,
  },
  createAccountEmphasis: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.bodySemibold,
  },
  createAccountLink: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    marginTop: 6,
    paddingHorizontal: 4,
  },
  createAccountText: {
    color: '#59668F',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 16,
    lineHeight: 22,
    textAlign: 'center',
  },
  decorativeLayer: {
    pointerEvents: 'none',
    zIndex: 0,
  },
  eyeButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    minWidth: 48,
  },
  field: {
    alignItems: 'center',
    borderColor: '#C8CEE5',
    borderRadius: 30,
    borderWidth: 2,
    flexDirection: 'row',
    minHeight: 56,
    paddingHorizontal: 12,
    width: '100%',
  },
  fieldIcon: {
    marginHorizontal: 6,
  },
  fontLoading: {
    backgroundColor: '#FEFDFA',
    flex: 1,
  },
  errorText: {
    color: '#B3261E',
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 18,
    marginTop: 10,
    textAlign: 'center',
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: 2,
  },
  forgotPasswordLabel: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 16,
    lineHeight: 22,
  },
  form: {
    alignSelf: 'stretch',
    gap: 12,
  },
  hero: {
    maxWidth: 310,
  },
  input: {
    color: '#59668F',
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 18,
    lineHeight: 24,
    minHeight: 52,
    paddingHorizontal: 8,
    paddingVertical: 0,
  },
  loginButton: {
    alignItems: 'center',
    backgroundColor: '#087B6F',
    borderRadius: 30,
    justifyContent: 'center',
    minHeight: 58,
    width: '100%',
  },
  loginButtonLabel: {
    color: '#FFFAF1',
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 21,
    lineHeight: 28,
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
    right: '-12%',
  },
  pressed: {
    opacity: 0.82,
  },
  privacyRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    marginTop: 18,
    maxWidth: 344,
    minHeight: 48,
    width: '100%',
  },
  privacyText: {
    color: '#59668F',
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 15,
    lineHeight: 21,
  },
  supportingCopy: {
    color: '#59668F',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 17,
    lineHeight: 24,
    marginTop: 4,
    textAlign: 'center',
  },
  title: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 40,
    lineHeight: 46,
    textAlign: 'center',
  },
  titleBlock: {
    alignItems: 'center',
    width: '100%',
  },
  wrapper: {
    backgroundColor: '#FEFDFA',
    flex: 1,
    overflow: 'hidden',
  },
});
