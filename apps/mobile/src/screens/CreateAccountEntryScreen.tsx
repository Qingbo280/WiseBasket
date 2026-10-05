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
const HERO_IMAGE = require('../../assets/images/auth/create-account-hero-basket.png');
const PLANT_LEFT_TOP_IMAGE = require('../../assets/images/auth/auth-plant-left-top.png');
const PLANT_RIGHT_MIDDLE_IMAGE = require('../../assets/images/auth/auth-plant-right-middle.png');
const PLANT_BOTTOM_LEFT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-left.png');
const PLANT_BOTTOM_RIGHT_IMAGE = require('../../assets/images/auth/auth-plant-bottom-right.png');

const HERO_ASPECT_RATIO = 970 / 1398;

export interface CreateAccountDetails {
  email: string;
  name: string;
  password: string;
}

export interface CreateAccountEntryScreenProps {
  createError?: string | null;
  onCreateAccount?: (details: CreateAccountDetails) => void | Promise<void>;
  onLogin?: () => void;
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
              {
            height: plantRightMiddleWidth * (1585 / 992),
            top: height * 0.24,
            right: width <= 384 ? '-18%' : '-12%',
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

interface CreateAccountFieldProps {
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  icon: ComponentProps<typeof MaterialCommunityIcons>['name'];
  keyboardType?: 'default' | 'email-address';
  onChangeText: (value: string) => void;
  placeholder: string;
  secureTextEntry?: boolean;
  trailing?: ReactNode;
  value: string;
}

function CreateAccountField({
  autoCapitalize = 'none',
  icon,
  keyboardType = 'default',
  onChangeText,
  placeholder,
  secureTextEntry = false,
  trailing,
  value,
}: CreateAccountFieldProps) {
  return (
    <View style={styles.field}>
      <MaterialCommunityIcons
        accessibilityElementsHidden
        color="#69749D"
        name={icon}
        size={27}
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

function VisibilityButton({ onPress, visible, label }: {
  label: string;
  onPress: () => void;
  visible: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      hitSlop={4}
      onPress={onPress}
      style={styles.eyeButton}
    >
      <MaterialCommunityIcons
        color="#69749D"
        name={visible ? 'eye-off-outline' : 'eye-outline'}
        size={27}
      />
    </Pressable>
  );
}

/** Static Create Account composition. Callbacks are intentionally UI-only in this pass. */
export function CreateAccountEntryScreen({
  createError = null,
  onCreateAccount = () => undefined,
  onLogin = () => undefined,
}: CreateAccountEntryScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [userName, setUserName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleCreateAccount = async () => {
    if (busy) return;
    const trimmedName = userName.trim();
    const trimmedEmail = email.trim();
    if (!trimmedName || !trimmedEmail || !password) {
      setValidationError('Fill in your name, email and password.');
      return;
    }
    if (password.length < 8) {
      setValidationError('Use at least 8 characters for your password.');
      return;
    }
    if (password !== confirmPassword) {
      setValidationError('Passwords do not match.');
      return;
    }
    setValidationError(null);
    setBusy(true);
    try {
      await onCreateAccount({ email: trimmedEmail, name: trimmedName, password });
    } catch (error) {
      setValidationError(
        error instanceof Error ? error.message : 'Could not create your account. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  };

  const { height, width } = useWindowDimensions();
  const horizontalPadding = width <= 360 ? 24 : width <= 384 ? 28 : 34;
  const compactHeight = height < 840;
  const logoWidth = Math.min(width * 0.56, 232);
  const heroWidth = Math.min(width * 0.62, 260);
  const heroHeight = heroWidth * HERO_ASPECT_RATIO;

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
            paddingTop: compactHeight ? 24 : 34,
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
            accessibilityLabel="WiseBasket basket character with vegetables, hearts, sparkles, and a green check badge"
            resizeMode="contain"
            source={HERO_IMAGE}
            style={[
              styles.hero,
              {
                height: heroHeight,
                marginTop: compactHeight ? 8 : 12,
                width: heroWidth,
              },
            ]}
          />

          <View style={styles.titleBlock}>
            <Text accessibilityRole="header" style={styles.title}>Create account</Text>
            <Text style={styles.supportingCopy}>Save your plan and continue anytime.</Text>
          </View>

          <View style={[styles.form, { marginTop: compactHeight ? 10 : 12 }]}>
            <CreateAccountField
              autoCapitalize="words"
              icon="account-outline"
              onChangeText={setUserName}
              placeholder="User name"
              value={userName}
            />
            <CreateAccountField
              icon="email-outline"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="Email address"
              value={email}
            />
            <CreateAccountField
              icon="lock"
              onChangeText={setPassword}
              placeholder="Password"
              secureTextEntry={!showPassword}
              trailing={(
                <VisibilityButton
                  label={showPassword ? 'Hide password' : 'Show password'}
                  onPress={() => setShowPassword((visible) => !visible)}
                  visible={showPassword}
                />
              )}
              value={password}
            />
            <Text style={styles.helperText}>Use at least 8 characters.</Text>
            <CreateAccountField
              icon="lock"
              onChangeText={setConfirmPassword}
              placeholder="Confirm password"
              secureTextEntry={!showConfirmPassword}
              trailing={(
                <VisibilityButton
                  label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                  onPress={() => setShowConfirmPassword((visible) => !visible)}
                  visible={showConfirmPassword}
                />
              )}
              value={confirmPassword}
            />
          </View>

          <Pressable
            accessibilityLabel="Create account"
            accessibilityRole="button"
            accessibilityState={{ busy }}
            disabled={busy}
            onPress={() => void handleCreateAccount()}
            style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.primaryButtonLabel}>
              {busy ? 'Creating your account…' : 'Create account'}
            </Text>
          </Pressable>
          {validationError || createError ? (
            <Text style={styles.errorText}>{validationError ?? createError}</Text>
          ) : null}

          <Pressable
            accessibilityLabel="Log in"
            accessibilityRole="button"
            onPress={onLogin}
            style={styles.loginLink}
          >
            <Text style={styles.loginLinkText}>
              Already have an account?{' '}
              <Text style={styles.loginLinkEmphasis}>Log in</Text>
            </Text>
          </Pressable>

          <View style={styles.privacyRow}>
            <MaterialCommunityIcons
              accessibilityElementsHidden
              color="#3F9B50"
              name="shield-check"
              size={34}
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
    paddingBottom: 18,
  },
  contentLayer: {
    alignItems: 'center',
    alignSelf: 'stretch',
    position: 'relative',
    zIndex: 1,
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
    borderRadius: 29,
    borderWidth: 2,
    flexDirection: 'row',
    minHeight: 56,
    paddingHorizontal: 11,
    width: '100%',
  },
  fieldIcon: {
    marginHorizontal: 6,
  },
  fontLoading: {
    backgroundColor: '#FEFDFA',
    flex: 1,
  },
  form: {
    alignSelf: 'stretch',
    gap: 7,
  },
  helperText: {
    color: '#59668F',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 14,
    lineHeight: 19,
    marginLeft: 16,
    marginTop: -2,
  },
  hero: {
    maxWidth: 260,
  },
  input: {
    color: '#59668F',
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 17,
    lineHeight: 22,
    minHeight: 52,
    paddingHorizontal: 8,
    paddingVertical: 0,
  },
  errorText: {
    color: '#B3261E',
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 18,
    marginTop: 10,
    textAlign: 'center',
  },
  loginLink: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: 4,
  },
  loginLinkEmphasis: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.bodySemibold,
  },
  loginLinkText: {
    color: '#59668F',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 15,
    lineHeight: 21,
    textAlign: 'center',
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
  pressed: {
    opacity: 0.82,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: '#087B6F',
    borderRadius: 30,
    justifyContent: 'center',
    marginTop: 10,
    minHeight: 56,
    width: '100%',
  },
  primaryButtonLabel: {
    color: '#FFFAF1',
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 20,
    lineHeight: 27,
  },
  privacyRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 9,
    justifyContent: 'center',
    marginTop: 3,
    maxWidth: 344,
    minHeight: 48,
    width: '100%',
  },
  privacyText: {
    color: '#59668F',
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 14,
    lineHeight: 20,
  },
  supportingCopy: {
    color: '#59668F',
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 16,
    lineHeight: 21,
    marginTop: 2,
    textAlign: 'center',
  },
  title: {
    color: '#064C4D',
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 36,
    lineHeight: 42,
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
