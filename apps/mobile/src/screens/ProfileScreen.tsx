import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFonts } from 'expo-font';
import { useState, type ComponentProps } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  priceCheckLocationFontAssets,
  priceCheckLocationFonts,
} from '../components/price-check/priceCheckLocationTokens';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export interface ProfileDetails {
  email: string;
  name: string;
}

export interface ProfileScreenProps {
  onBack: () => void;
  onLogout: () => void;
  onPersonalizationPress: () => void;
  onProfileChange: (profile: ProfileDetails) => void;
  profile: ProfileDetails;
  saveError?: string | null;
}

function ProfileField({
  autoCapitalize,
  editable = true,
  icon,
  keyboardType,
  label,
  onChangeText,
  value,
}: {
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  editable?: boolean;
  icon: IconName;
  keyboardType?: 'default' | 'email-address';
  label: string;
  onChangeText: (value: string) => void;
  value: string;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.field}>
        <MaterialCommunityIcons
          accessibilityElementsHidden
          color={COLORS.muted}
          name={icon}
          size={23}
          style={styles.fieldIcon}
        />
        <TextInput
          accessibilityLabel={label}
          autoCapitalize={autoCapitalize}
          autoCorrect={false}
          editable={editable}
          keyboardType={keyboardType}
          onChangeText={onChangeText}
          style={styles.input}
          value={value}
        />
      </View>
    </View>
  );
}

export function ProfileScreen({
  onBack,
  onLogout,
  onPersonalizationPress,
  onProfileChange,
  profile,
  saveError = null,
}: ProfileScreenProps) {
  const [fontsLoaded] = useFonts(priceCheckLocationFontAssets);
  const [draft, setDraft] = useState(profile);

  if (!fontsLoaded) {
    return <View style={styles.fontLoading} />;
  }

  const updateProfile = (nextProfile: ProfileDetails) => {
    setDraft(nextProfile);
    onProfileChange(nextProfile);
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topBar}>
          <Pressable
            accessibilityLabel="Back"
            accessibilityRole="button"
            onPress={onBack}
            style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}
          >
            <MaterialCommunityIcons color={COLORS.deepTeal} name="arrow-left" size={30} />
          </Pressable>
          <Text accessibilityRole="header" style={styles.pageTitle}>Profile</Text>
          <View style={styles.topBarSpacer} />
        </View>

        <View style={styles.profileCard}>
          <View accessibilityLabel="Profile" style={styles.profileIcon}>
            <MaterialCommunityIcons color={COLORS.deepTeal} name="account-circle-outline" size={58} />
          </View>
          <Text style={styles.cardTitle}>Your details</Text>
          <Text style={styles.cardCopy}>Keep your WiseBasket details up to date.</Text>
        </View>

        <View style={styles.formCard}>
          <ProfileField
            autoCapitalize="words"
            icon="account-outline"
            label="Name"
            onChangeText={(name) => updateProfile({ ...draft, name })}
            value={draft.name}
          />
          <ProfileField
            editable={false}
            icon="email-outline"
            keyboardType="email-address"
            label="Email"
            onChangeText={(email) => updateProfile({ ...draft, email })}
            value={draft.email}
          />
        </View>

        {saveError ? <Text accessibilityRole="alert" style={styles.saveError}>{saveError}</Text> : null}

        <Pressable
          accessibilityLabel="Personalization"
          accessibilityRole="button"
          onPress={onPersonalizationPress}
          style={({ pressed }) => [styles.personalizationCard, pressed && styles.pressed]}
        >
          <View style={styles.personalizationIcon}>
            <MaterialCommunityIcons color={COLORS.deepTeal} name="tune-variant" size={25} />
          </View>
          <View style={styles.personalizationCopy}>
            <Text style={styles.personalizationTitle}>Personalization</Text>
            <Text style={styles.personalizationDescription}>
              Update your household, meals, budget and usual foods.
            </Text>
          </View>
          <MaterialCommunityIcons color={COLORS.deepTeal} name="chevron-right" size={28} />
        </Pressable>

        <Pressable
          accessibilityLabel="Log out"
          accessibilityRole="button"
          onPress={onLogout}
          style={({ pressed }) => [styles.logoutButton, pressed && styles.pressed]}
        >
          <MaterialCommunityIcons color={COLORS.coral} name="logout" size={23} />
          <Text style={styles.logoutLabel}>Log out</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const COLORS = {
  background: '#FAF7F2',
  coral: '#D95D4C',
  deepTeal: '#183F36',
  muted: '#66766F',
  paleGreen: '#EAF5EE',
  surface: '#FFFFFF',
  line: '#D9E8E0',
} as const;

const styles = StyleSheet.create({
  cardCopy: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 16,
    lineHeight: 23,
    marginTop: 4,
    textAlign: 'center',
  },
  cardTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 24,
    lineHeight: 30,
    marginTop: 12,
  },
  saveError: {
    color: '#B3261E',
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 10,
    textAlign: 'center',
  },
  content: {
    flexGrow: 1,
    paddingBottom: 32,
    paddingHorizontal: 24,
    paddingTop: 20,
  },
  field: {
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderColor: COLORS.line,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    minHeight: 56,
    paddingHorizontal: 16,
  },
  fieldGroup: {
    gap: 8,
  },
  fieldIcon: {
    marginRight: 10,
  },
  fieldLabel: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 15,
    lineHeight: 20,
  },
  formCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 24,
    gap: 18,
    marginTop: 20,
    padding: 20,
  },
  fontLoading: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  iconButton: {
    alignItems: 'center',
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  input: {
    color: COLORS.deepTeal,
    flex: 1,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 17,
    lineHeight: 23,
    minHeight: 54,
    paddingVertical: 0,
  },
  personalizationCard: {
    alignItems: 'center',
    backgroundColor: COLORS.paleGreen,
    borderRadius: 20,
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
    minHeight: 82,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  personalizationCopy: {
    flex: 1,
    minWidth: 0,
  },
  personalizationDescription: {
    color: COLORS.muted,
    fontFamily: priceCheckLocationFonts.body,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 2,
  },
  personalizationIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  personalizationTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 17,
    lineHeight: 22,
  },
  logoutButton: {
    alignItems: 'center',
    borderColor: COLORS.coral,
    borderRadius: 18,
    borderWidth: 1.5,
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'center',
    marginTop: 24,
    minHeight: 52,
  },
  logoutLabel: {
    color: COLORS.coral,
    fontFamily: priceCheckLocationFonts.bodySemibold,
    fontSize: 17,
    lineHeight: 22,
  },
  pageTitle: {
    color: COLORS.deepTeal,
    fontFamily: priceCheckLocationFonts.heading,
    fontSize: 30,
    lineHeight: 36,
  },
  pressed: {
    opacity: 0.78,
  },
  profileCard: {
    alignItems: 'center',
    backgroundColor: COLORS.paleGreen,
    borderRadius: 28,
    marginTop: 22,
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  profileIcon: {
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 48,
    height: 88,
    justifyContent: 'center',
    width: 88,
  },
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  topBar: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 48,
  },
  topBarSpacer: {
    height: 48,
    width: 48,
  },
});
